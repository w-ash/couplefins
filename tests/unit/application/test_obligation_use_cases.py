"""US-HOUSE-13: the obligation use cases' branches that the route tests in
tests/integration/api/test_house_loans.py cannot see."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import attrs
import pytest

from src.application.use_cases._shared.house_records import ObligationTerms
from src.application.use_cases.add_loan_payment_obligations import (
    AddLoanPaymentObligationsCommand,
    AddLoanPaymentObligationsUseCase,
)
from src.application.use_cases.create_obligation import (
    CreateObligationCommand,
    CreateObligationUseCase,
)
from src.application.use_cases.find_obligation_payment_candidates import (
    FindObligationPaymentCandidatesCommand,
    FindObligationPaymentCandidatesUseCase,
)
from src.application.use_cases.mark_obligation_paid import (
    MarkObligationPaidCommand,
    MarkObligationPaidUseCase,
)
from src.application.use_cases.update_obligation import (
    UpdateObligationCommand,
    UpdateObligationUseCase,
)
from src.domain.entities.obligation import Obligation
from src.domain.exceptions import ValidationError
from tests.fixtures.factories import (
    make_co_owned_asset,
    make_loan,
    make_obligation,
    make_transaction,
)
from tests.fixtures.mocks import make_mock_uow

ASSET = make_co_owned_asset()
LOAN = make_loan(asset_id=ASSET.id, first_due_on=date(2026, 1, 31), term_months=None)
TAX_TERMS = ObligationTerms(
    kind="property_tax",
    description="Property tax, first installment",
    amount=Decimal("2430.555"),
    is_estimate=True,
    due_on=date(2026, 11, 1),
    late_after=date(2026, 12, 10),
    pays_from="  property-tax ",
)


def _uow(*obligations: Obligation) -> AsyncMock:
    uow = make_mock_uow()
    uow.co_owned_assets.get_current.return_value = ASSET
    uow.loans.get_by_id.side_effect = {LOAN.id: LOAN}.get
    uow.obligations.get_by_id.side_effect = {o.id: o for o in obligations}.get
    uow.obligations.get_by_asset_id.return_value = list(obligations)
    return uow


async def test_a_loan_of_another_home_is_refused() -> None:
    stranger = make_loan()
    uow = _uow()
    uow.loans.get_by_id.side_effect = {stranger.id: stranger}.get
    terms = attrs.evolve(TAX_TERMS, kind="loan_payment", loan_id=stranger.id)

    with pytest.raises(ValidationError, match="not this home"):
        await CreateObligationUseCase().execute(CreateObligationCommand(terms), uow)


async def test_an_update_replaces_the_values_and_keeps_the_paying_row() -> None:
    row = make_transaction()
    current = make_obligation(asset_id=ASSET.id, paid_by_transaction_id=row.id)
    billed = attrs.evolve(TAX_TERMS, amount=Decimal("2512.40"), is_estimate=False)

    result = await UpdateObligationUseCase().execute(
        UpdateObligationCommand(obligation_id=current.id, terms=billed), _uow(current)
    )

    updated = result.obligation
    assert (updated.id, updated.asset_id, updated.paid_by_transaction_id) == (
        current.id,
        ASSET.id,
        row.id,
    )
    assert (updated.amount, updated.is_estimate, updated.pays_from) == (
        Decimal("2512.40"),
        False,
        "property-tax",
    )


async def test_a_money_in_row_cannot_pay_an_obligation() -> None:
    obligation = make_obligation()
    uow = _uow(obligation)
    uow.transactions.get_by_id.return_value = make_transaction(amount=Decimal(50))

    with pytest.raises(ValidationError, match="money out"):
        await MarkObligationPaidUseCase().execute(
            MarkObligationPaidCommand(obligation.id, make_transaction().id), uow
        )
    uow.obligations.save.assert_not_awaited()


async def test_candidates_read_the_window_and_know_the_loan_and_linked_rows() -> None:
    payment = make_obligation(
        asset_id=ASSET.id,
        kind="loan_payment",
        loan_id=LOAN.id,
        amount=LOAN.payment,
        due_on=date(2026, 11, 1),
    )
    tagged = make_transaction(
        amount=Decimal("-40.00"), date=date(2026, 12, 10), tags=("loan:mortgage",)
    )
    taken = make_transaction(amount=-LOAN.payment, date=date(2026, 11, 1))
    paid = make_obligation(asset_id=ASSET.id, paid_by_transaction_id=taken.id)
    uow = _uow(payment, paid)
    uow.transactions.get_by_date_range.return_value = [taken, tagged]

    result = await FindObligationPaymentCandidatesUseCase().execute(
        FindObligationPaymentCandidatesCommand(payment.id), uow
    )

    assert [(c.transaction, c.score) for c in result.candidates] == [(tagged, 2)]
    uow.transactions.get_by_date_range.assert_awaited_once_with(
        date(2026, 11, 1) - timedelta(days=14),
        date(2026, 11, 1) + timedelta(days=45),
        tags=None,
    )
    uow.obligations.get_by_asset_id.assert_awaited_once_with(ASSET.id)


async def test_generated_payments_skip_months_that_have_one() -> None:
    uow = _uow()
    january = make_obligation(
        kind="loan_payment", loan_id=LOAN.id, due_on=date(2026, 1, 31)
    )
    uow.obligations.get_by_loan_id.return_value = [january]

    result = await AddLoanPaymentObligationsUseCase().execute(
        AddLoanPaymentObligationsCommand(
            loan_id=LOAN.id, months=3, today=date(2026, 1, 17)
        ),
        uow,
    )

    assert [o.due_on for o in result.obligations] == [
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
    ]
    uow.obligations.save_batch.assert_awaited_once_with(result.obligations)
    uow.commit.assert_awaited_once()
