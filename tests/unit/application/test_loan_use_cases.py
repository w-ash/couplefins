"""US-HOUSE-12: the loan use cases' branches that the route tests in
tests/integration/api/test_house_loans.py cannot see."""

from datetime import date

import attrs

from src.application.use_cases.close_loan import CloseLoanCommand, CloseLoanUseCase
from src.application.use_cases.delete_loan import DeleteLoanCommand, DeleteLoanUseCase
from src.domain.entities.obligation import Obligation
from tests.fixtures.factories import make_loan, make_obligation, make_transaction
from tests.fixtures.mocks import make_mock_uow


async def test_closing_drops_only_the_unpaid_payments_due_after_the_day() -> None:
    loan = make_loan()
    uow = make_mock_uow()
    uow.loans.get_by_id.return_value = loan

    def payment(due_on: date, *, paid: bool = False) -> Obligation:
        return make_obligation(
            kind="loan_payment",
            loan_id=loan.id,
            due_on=due_on,
            paid_by_transaction_id=make_transaction().id if paid else None,
        )

    kept_paid = payment(date(2026, 7, 1), paid=True)
    kept_due = payment(date(2026, 5, 1))
    dropped = payment(date(2026, 7, 1))
    uow.obligations.get_by_loan_id.return_value = [kept_due, kept_paid, dropped]

    result = await CloseLoanUseCase().execute(
        CloseLoanCommand(loan_id=loan.id, closed_on=date(2026, 6, 15)), uow
    )

    assert result.loan == attrs.evolve(loan, closed_on=date(2026, 6, 15))
    uow.obligations.delete_by_ids.assert_awaited_once_with([dropped.id])
    uow.commit.assert_awaited_once()


async def test_delete_reads_only_the_loans_own_tag() -> None:
    """One prefix read for `loan:mortgage`; a `loan:mortgage-2` row it also
    returns does not block the delete."""
    loan = make_loan(name="Mortgage")
    uow = make_mock_uow()
    uow.loans.get_by_id.return_value = loan
    uow.transactions.get_by_tag_prefixes.return_value = [
        make_transaction(tags=("loan:mortgage-2",))
    ]

    result = await DeleteLoanUseCase().execute(DeleteLoanCommand(loan.id), uow)

    assert result.deleted is True
    uow.transactions.get_by_tag_prefixes.assert_awaited_once_with(("loan:mortgage",))
    uow.loans.exists_replaced_by.assert_awaited_once_with(loan.id)
    uow.loans.get_by_asset_id.assert_not_awaited()
    uow.loans.delete.assert_awaited_once_with(loan.id)
