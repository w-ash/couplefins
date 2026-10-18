"""The reads module is the only place use cases read transaction lists,
and the only place the transfer rule is applied. Two grep gates enforce it."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
import re
from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from src.application.use_cases._shared.reconciliation_context import (
    ReconciliationContext,
    load_reconciliation_context,
)
from src.application.use_cases._shared.transaction_reads import (
    NO_SHARES,
    TagFilter,
    fetch_account_rows,
    fetch_all_settlement_rows,
    fetch_house_rows,
    fetch_latest_spending_month,
    fetch_listed_rows,
    fetch_payer_rows,
    fetch_scoped_rows,
    fetch_settlement_rows,
    fetch_year_spending_rows,
    resolve_period,
    row_shares,
    with_shares,
)
from src.domain.exceptions import ValidationError
from src.domain.repositories.transaction_repository import (
    TransactionRepositoryProtocol,
)
from tests.fixtures.factories import (
    ALICE,
    BOB,
    make_income_group,
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
    "get_by_account_ids",
    "get_by_tag_prefix",
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
    uow.persons.get_all.return_value = [ALICE, BOB]
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
    shared = TagFilter(tags=("shared",))
    assert await fetch_settlement_rows(uow, ctx, WINDOW, tag_filter=shared) == [dinner]
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


async def test_a_tag_prefix_keeps_rows_with_a_tag_in_its_namespace() -> None:
    """The database filters by containment; the prefix filters in memory,
    in every read that takes tags."""
    uow, ctx = await _ctx()
    mortgage = make_transaction(
        tags=("shared", "line:mortgage"), payer_person_id=ALICE.id
    )
    pot_only = make_transaction(tags=("shared", "pot:line"), payer_person_id=ALICE.id)
    lines = TagFilter(tags=("shared",), prefix="line:")
    for read in (
        uow.transactions.get_household_by_date_range,
        uow.transactions.get_by_date_range,
        uow.transactions.get_settlement_relevant_by_date_range,
    ):
        read.return_value = [mortgage, pot_only]

    scoped = await fetch_scoped_rows(uow, ctx, WINDOW, "household", tag_filter=lines)
    assert (scoped.listed, scoped.spending) == ([mortgage], [mortgage])
    assert await fetch_listed_rows(uow, WINDOW, tag_filter=lines) == [mortgage]
    assert await fetch_settlement_rows(uow, ctx, WINDOW, tag_filter=lines) == [mortgage]
    uow.transactions.get_by_date_range.assert_awaited_once_with(
        *WINDOW, tags=("shared",)
    )


@pytest.mark.parametrize("prefix", ["line", "line:mortgage", "Line:", ""])
def test_a_tag_prefix_must_be_a_namespace(prefix: str) -> None:
    with pytest.raises(ValidationError, match="tag_prefix"):
        TagFilter(prefix=prefix)


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
        excluding_categories=ctx.non_spending_categories, year=None
    )
    assert "Credit Card Payment" in ctx.non_spending_categories


async def test_resolve_period_anchors_within_a_named_year() -> None:
    """One rule for both branches: the latest month with spending. A named
    year scopes the anchor to itself rather than borrowing today's month."""
    uow, ctx = await _ctx()
    uow.transactions.get_latest_household_transaction_date.return_value = date(
        2024, 11, 4
    )

    assert await resolve_period(uow, ctx, 2024, None) == (2024, 11)
    uow.transactions.get_latest_household_transaction_date.assert_called_once_with(
        excluding_categories=ctx.non_spending_categories, year=2024
    )


async def test_resolve_period_takes_an_explicit_month_without_asking() -> None:
    """Both named leaves nothing to resolve, so the anchor query is skipped."""
    uow, ctx = await _ctx()

    assert await resolve_period(uow, ctx, 2024, 3) == (2024, 3)
    uow.transactions.get_latest_household_transaction_date.assert_not_called()


async def test_resolve_period_falls_back_to_today_in_an_empty_year() -> None:
    uow, ctx = await _ctx()
    uow.transactions.get_latest_household_transaction_date.return_value = None

    year, month = await resolve_period(uow, ctx, 2024, None)
    assert (year, month) == (2024, datetime.now(UTC).month)


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
    uow.persons.get_all.return_value = [ALICE, BOB]
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
    bob = BOB
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


async def test_account_rows_are_every_row_of_the_accounts() -> None:
    uow = make_mock_uow()
    dinner, card, _ = _rows()
    uow.transactions.get_by_account_ids.return_value = [dinner, card]

    assert await fetch_account_rows(uow, [dinner.account_id]) == [dinner, card]
    uow.transactions.get_by_account_ids.assert_awaited_once_with([dinner.account_id])


async def test_house_rows_read_each_row_once_through_the_date() -> None:
    """The share rows outside the joint accounts are read apart; the joint
    ones come from the joint rows. Every row is cut off at `through`."""
    uow = make_mock_uow()
    joint_id = make_transaction(joint=True).account_id
    deposit = make_transaction(joint=True, amount=Decimal("500.00"))
    premium = make_transaction(joint=True, tags=("share:insurance",))
    later = make_transaction(joint=True, tags=("share:closing",), date=date(2026, 2, 1))
    wire = make_transaction(
        category="Credit Card Payment", tags=("share:closing",), is_excluded=True
    )
    uow.transactions.get_by_account_ids.return_value = [deposit, premium, later]
    uow.transactions.get_by_tag_prefix.return_value = [wire]

    rows = await fetch_house_rows(uow, [joint_id], date(2026, 1, 31), with_shares=True)

    assert rows.joint == [deposit, premium]
    assert rows.shares == [premium, wire]
    uow.transactions.get_by_tag_prefix.assert_awaited_once_with(
        "share:", excluding_account_ids=[joint_id]
    )
    uow.categories.get_all.assert_not_called()


async def test_house_rows_without_shares_read_no_share_rows() -> None:
    uow = make_mock_uow()
    premium = make_transaction(joint=True, tags=("share:insurance",))
    uow.transactions.get_by_account_ids.return_value = [premium]

    rows = await fetch_house_rows(
        uow, [premium.account_id], date(2026, 12, 31), with_shares=False
    )

    assert (rows.joint, rows.shares) == ([premium], [])
    uow.transactions.get_by_tag_prefix.assert_not_called()


async def test_payer_rows_leave_out_joint_rows_at_the_read() -> None:
    uow = make_mock_uow()
    venmo = make_transaction(category="Credit Card Payment")
    uow.transactions.get_by_date_range.return_value = [venmo]

    assert await fetch_payer_rows(uow, WINDOW) == [venmo]
    uow.transactions.get_by_date_range.assert_awaited_once_with(
        *WINDOW, payer_only=True
    )


# --- Row shares: computed once, here, for every listed row ---


async def _couple_ctx() -> ReconciliationContext:
    uow = make_mock_uow()
    uow.persons.get_all.return_value = [ALICE, BOB]
    transfer, card = make_transfer_group()
    uow.category_groups.get_all.return_value = [transfer]
    uow.categories.get_all.return_value = [card]
    return await load_reconciliation_context(uow)


async def test_row_shares_split_a_spending_row() -> None:
    ctx = await _couple_ctx()
    tx = make_transaction(
        payer_person_id=BOB.id, payer_percentage=70, amount=Decimal("-100.00")
    )

    shares = row_shares(tx, ctx)

    assert shares.percentages == {BOB.id: 70, ALICE.id: 30}
    assert shares.amounts == {BOB.id: Decimal("70.00"), ALICE.id: Decimal("30.00")}


async def test_a_transfer_has_no_shares_unless_it_is_a_joint_deposit() -> None:
    ctx = await _couple_ctx()
    card = make_transaction(category="Credit Card Payment", payer_person_id=ALICE.id)
    deposit = make_transaction(
        joint=True,
        category="Credit Card Payment",
        amount=Decimal("1500.00"),
        depositor_person_id=BOB.id,
    )

    assert row_shares(card, ctx) == NO_SHARES
    assert row_shares(deposit, ctx).percentages == {ALICE.id: 0, BOB.id: 100}


async def test_a_row_whose_payer_left_the_couple_has_no_shares() -> None:
    """Stale data logs a warning; the read still answers."""
    ctx = await _couple_ctx()
    stale = make_transaction(payer_person_id=uuid4())

    with capture_logs() as logs:
        shares = with_shares([stale], ctx)

    assert shares == {stale.id: NO_SHARES}
    assert [log["event"] for log in logs] == ["transaction_shares_unresolved"]
