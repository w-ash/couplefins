"""The reads module is the only place use cases read transaction lists,
and the only place the transfer rule is applied. Two grep gates enforce it."""

from datetime import date
from decimal import Decimal
from pathlib import Path
import re

from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.application.use_cases._shared.transaction_reads import (
    fetch_all_settlement_rows,
    fetch_latest_spending_month,
    fetch_listed_rows,
    fetch_scoped_rows,
    fetch_settlement_rows,
    fetch_year_spending_rows,
)
from src.domain.repositories.transaction_repository import (
    TransactionRepositoryProtocol,
)
from tests.fixtures.factories import (
    ALICE,
    make_income_group,
    make_person,
    make_transaction,
    make_transfer_group,
)
from tests.fixtures.mocks import make_mock_uow

_APPLICATION = Path(__file__).resolve().parents[3] / "src" / "application"
_READS_MODULE = _APPLICATION / "use_cases" / "_shared" / "transaction_reads.py"
_LIST_READS = {
    "get_household_by_year",
    "get_by_year",
    "get_by_date_range",
    "get_household_by_date_range",
    "get_settlement_relevant_by_date_range",
    "get_all_settlement_relevant",
    "get_by_person_and_date_range",
}
# Scalar reads that still answer "what spending exists?" and so must apply
# the transfer rule the same way the list reads do.
_SCALAR_READS = {"get_latest_household_transaction_date"}
_GATED_READS = _LIST_READS | _SCALAR_READS
WINDOW = (date(2026, 1, 1), date(2026, 1, 31))


def _rows():
    dinner = make_transaction(category="Dining Out", payer_person_id=ALICE.id)
    card = make_transaction(category="Credit Card Payment", payer_person_id=ALICE.id)
    personal = make_transaction(
        category="Dining Out", household=False, payer_person_id=ALICE.id, tags=()
    )
    return dinner, card, personal


async def _ctx():
    uow = make_mock_uow()
    transfer, card_payment = make_transfer_group()
    uow.persons.get_all.return_value = [
        make_person(name="Alice"),
        make_person(name="Bob"),
    ]
    uow.category_groups.get_all.return_value = [transfer]
    uow.categories.get_all.return_value = [card_payment]
    return uow, await load_reconciliation_context(uow)


async def test_year_rows_drop_transfers_under_both_scopes() -> None:
    uow, ctx = await _ctx()
    dinner, card, personal = _rows()
    uow.transactions.get_household_by_year.return_value = [dinner, card]
    uow.transactions.get_by_year.return_value = [dinner, card, personal]

    assert await fetch_year_spending_rows(uow, 2026, "household", ctx) == [dinner]
    assert await fetch_year_spending_rows(uow, 2026, "personal", ctx) == [
        dinner,
        personal,
    ]


async def test_settlement_rows_drop_transfers_and_forward_tags() -> None:
    uow, ctx = await _ctx()
    dinner, card, _ = _rows()
    uow.transactions.get_all_settlement_relevant.return_value = [dinner, card]
    uow.transactions.get_settlement_relevant_by_date_range.return_value = [dinner, card]

    assert await fetch_all_settlement_rows(uow, ctx) == [dinner]
    assert await fetch_settlement_rows(uow, ctx, WINDOW, tags=("shared",)) == [dinner]
    uow.transactions.get_settlement_relevant_by_date_range.assert_called_once_with(
        *WINDOW, tags=("shared",)
    )


async def test_scoped_rows_list_transfers_but_do_not_spend_them() -> None:
    uow, ctx = await _ctx()
    dinner, card, personal = _rows()
    uow.transactions.get_household_by_date_range.return_value = [dinner, card]
    uow.transactions.get_by_person_and_date_range.return_value = [dinner, personal]
    uow.transactions.get_by_date_range.return_value = [dinner, card, personal]

    household = await fetch_scoped_rows(uow, ctx, WINDOW, "household")
    assert (household.listed, household.spending) == ([dinner, card], [dinner])

    personal_rows = await fetch_scoped_rows(uow, ctx, WINDOW, "personal", ALICE.id)
    assert (personal_rows.listed, personal_rows.spending) == (
        [dinner, card, personal],
        [dinner, personal],
    )

    both = await fetch_scoped_rows(uow, ctx, WINDOW, "all", ALICE.id)
    assert both.listed == [dinner, card, personal]
    assert both.spending == [dinner, personal]


async def test_listed_rows_keep_transfers_and_never_touch_categories() -> None:
    uow = make_mock_uow()
    dinner, card, _ = _rows()
    uow.transactions.get_by_date_range.return_value = [dinner, card]

    assert await fetch_listed_rows(uow, WINDOW) == [dinner, card]
    uow.categories.get_all.assert_not_called()
    uow.category_groups.get_all.assert_not_called()


async def test_latest_spending_month_excludes_transfer_categories() -> None:
    uow, ctx = await _ctx()
    uow.transactions.get_latest_household_transaction_date.return_value = date(
        2026, 2, 10
    )

    assert await fetch_latest_spending_month(uow, ctx) == (2026, 2)
    uow.transactions.get_latest_household_transaction_date.assert_called_once_with(
        excluding_categories=ctx.non_spending_categories
    )
    assert "Credit Card Payment" in ctx.non_spending_categories


async def test_latest_spending_month_is_none_without_rows() -> None:
    uow, ctx = await _ctx()
    uow.transactions.get_latest_household_transaction_date.return_value = None

    assert await fetch_latest_spending_month(uow, ctx) is None


def test_reads_named_here_still_exist_on_the_protocol() -> None:
    assert set(dir(TransactionRepositoryProtocol)) >= _GATED_READS


def test_no_use_case_reads_transactions_directly() -> None:
    pattern = re.compile(r"\.transactions\.(" + "|".join(sorted(_GATED_READS)) + r")\(")
    offenders = [
        str(path.relative_to(_APPLICATION.parent.parent))
        for path in _APPLICATION.rglob("*.py")
        if path != _READS_MODULE and pattern.search(path.read_text())
    ]
    assert offenders == [], f"read transactions via transaction_reads: {offenders}"


def test_transfer_rule_is_applied_only_in_the_reads_module() -> None:
    offenders = [
        str(path.relative_to(_APPLICATION.parent.parent))
        for path in _APPLICATION.rglob("*.py")
        if path != _READS_MODULE and "exclude_non_spending" in path.read_text()
    ]
    assert offenders == [], (
        f"exclude_non_spending belongs in transaction_reads: {offenders}"
    )


async def test_income_rows_are_not_spending_under_any_scope() -> None:
    """A paycheck is money in: listed, badged, never a (negative) expense."""
    uow = make_mock_uow()
    transfer, card_payment = make_transfer_group()
    income, paychecks = make_income_group()
    uow.persons.get_all.return_value = [ALICE]
    uow.category_groups.get_all.return_value = [transfer, income]
    uow.categories.get_all.return_value = [card_payment, paychecks]
    ctx = await load_reconciliation_context(uow)
    dinner, _, _ = _rows()
    paycheck = make_transaction(
        category="Paychecks",
        household=False,
        payer_person_id=ALICE.id,
        payer_percentage=100,
        amount=Decimal("5000.00"),
        tags=(),
    )
    uow.transactions.get_by_year.return_value = [dinner, paycheck]
    uow.transactions.get_by_date_range.return_value = [dinner, paycheck]

    assert await fetch_year_spending_rows(uow, 2026, "personal", ctx) == [dinner]
    rows = await fetch_scoped_rows(uow, ctx, WINDOW, "personal", ALICE.id)
    assert (rows.listed, rows.spending) == ([dinner, paycheck], [dinner])
    assert ctx.category_kinds["Paychecks"] == "income"


async def test_personal_scope_is_every_row_where_my_share_is_positive() -> None:
    """The Transactions personal list reconciles to Insights "My Spending":
    my share of household splits, my own rows, and what my partner spotted
    for me — never a row where my share is zero."""
    uow, ctx = await _ctx()
    bob = make_person(name="Bob")
    split_rent = make_transaction(
        category="Rent", payer_person_id=bob.id, payer_percentage=50
    )
    partner_ticket = make_transaction(
        category="Concerts", payer_person_id=bob.id, payer_percentage=100
    )
    spotted_for_me = make_transaction(
        category="Parking", household=False, payer_person_id=bob.id, payer_percentage=0
    )
    i_spotted = make_transaction(
        category="Parking",
        household=False,
        payer_person_id=ALICE.id,
        payer_percentage=0,
    )
    uow.transactions.get_by_date_range.return_value = [
        split_rent,
        partner_ticket,
        spotted_for_me,
        i_spotted,
    ]

    rows = await fetch_scoped_rows(uow, ctx, WINDOW, "personal", ALICE.id)

    assert rows.listed == [split_rent, spotted_for_me]
    uow.transactions.get_by_date_range.assert_called_once_with(*WINDOW, tags=None)
