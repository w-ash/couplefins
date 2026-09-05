"""Budget, Insights, and the Dashboard read one lens and one accumulator,
so their numbers agree exactly for the same rows — pinned here so they
cannot drift again. The one deliberate difference: Budget's household view
also admits `include_personal` categories (US-BUDGET-4), which Insights and
the Dashboard never do; `test_include_personal_adds_exactly_the_opted_in_rows`
quantifies that gap."""

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from src.domain.budget import (
    BudgetOverview,
    BudgetOverviewInputs,
    compute_budget_overview,
)
from src.domain.insights import compute_comparison_cards, compute_spending_trends
from src.domain.spending_lens import (
    HouseholdLens,
    PersonalLens,
    SpendingLens,
    total_spending,
)
from tests.fixtures.factories import ALICE, BOB, make_category_group, make_transaction

FOOD = make_category_group(name="Food & Dining")
TRAVEL = make_category_group(name="Travel")
GROUPS = [FOOD, TRAVEL]
LOOKUP = {
    "Dining Out": (FOOD.id, FOOD.name),
    "Groceries": (FOOD.id, FOOD.name),
    "Flights": (TRAVEL.id, TRAVEL.name),
}
D = Decimal


def _household(month: int, category: str, amount: str, payer: UUID, pct: int):
    return make_transaction(
        date=date(2026, month, 3),
        category=category,
        amount=D(amount),
        payer_person_id=payer,
        payer_percentage=pct,
    )


def _personal(month: int, category: str, amount: str, payer: UUID, pct: int, tags=()):
    return make_transaction(
        date=date(2026, month, 4),
        category=category,
        amount=D(amount),
        payer_person_id=payer,
        payer_percentage=pct,
        household=False,
        tags=tags,
    )


ROWS = [
    _household(1, "Dining Out", "-100.00", ALICE.id, 50),
    _household(1, "Dining Out", "-40.00", BOB.id, 50),
    _household(1, "Flights", "-300.00", ALICE.id, 100),  # own ticket, household
    _household(1, "Flights", "-250.00", BOB.id, 100),
    _personal(2, "Groceries", "-30.00", ALICE.id, 0, ("bob",)),  # spotted for Bob
    _personal(2, "Groceries", "-24.00", BOB.id, 0, ("alice",)),  # spotted for Alice
    _personal(2, "Groceries", "-55.00", ALICE.id, 100),  # Alice's own
    _personal(2, "Dining Out", "-70.00", BOB.id, 70),  # personal split
    _household(3, "Dining Out", "33.33", ALICE.id, 50),  # household refund
    _personal(3, "Groceries", "10.00", ALICE.id, 100),  # personal refund
    make_transaction(date=date(2026, 3, 5), amount=D("-99.00"), is_excluded=True),
    make_transaction(date=date(2026, 3, 6), amount=D("-1981.00"), is_settlement=True),
    _household(3, "Mystery", "-12.34", BOB.id, 50),  # unmapped category
]
LENSES = [HouseholdLens(), PersonalLens(ALICE.id), PersonalLens(BOB.id)]
PERSON_IDS = [None, ALICE.id, BOB.id]


def _budget(lens: SpendingLens, month: int) -> BudgetOverview:
    return compute_budget_overview(
        BudgetOverviewInputs([], [], ROWS, LOOKUP, GROUPS, 2026, month), lens
    )


@pytest.mark.parametrize(("lens", "person_id"), zip(LENSES, PERSON_IDS, strict=True))
def test_budget_and_insights_agree_per_group(
    lens: SpendingLens, person_id: UUID | None
) -> None:
    budget = _budget(lens, 3)
    trends = compute_spending_trends(
        ROWS, LOOKUP, 2026, through_month=3, person_id=person_id
    )
    cards = compute_comparison_cards(ROWS, LOOKUP, 3, person_id=person_id)

    assert {s.group_id: s.ytd_spent for s in budget.group_statuses if s.ytd_spent} == {
        g.group_id: g.ytd_total for g in trends.group_summaries if g.ytd_total
    }
    assert {
        s.group_id: sum(c.transaction_count for c in s.ytd_categories)
        for s in budget.group_statuses
        if s.ytd_spent
    } == {
        g.group_id: g.transaction_count for g in trends.group_summaries if g.ytd_total
    }
    assert {
        s.group_id: s.monthly_spent for s in budget.group_statuses if s.monthly_spent
    } == {c.group_id: c.current_month_amount for c in cards if c.current_month_amount}


@pytest.mark.parametrize("lens", LENSES, ids=type)
def test_budget_total_matches_the_dashboard_path(lens: SpendingLens) -> None:
    month_rows = [tx for tx in ROWS if tx.date.month == 2]
    budget = _budget(lens, 2)
    assert sum((s.monthly_spent for s in budget.group_statuses), D(0)) == (
        total_spending(lens, month_rows)
    )


def test_partners_personal_views_sum_to_household_view() -> None:
    """Every household row is split between the two partners, so their
    personal views of household rows add up to the household view exactly."""
    household_rows = [tx for tx in ROWS if tx.household]
    alice = total_spending(PersonalLens(ALICE.id), household_rows)
    bob = total_spending(PersonalLens(BOB.id), household_rows)
    assert alice + bob == total_spending(HouseholdLens(), household_rows)


def test_include_personal_adds_exactly_the_opted_in_rows() -> None:
    """Budget's household view with `include_personal` categories exceeds
    the plain household lens — the one Insights and the Dashboard use — by
    exactly the opted-in personal rows, and nothing else."""
    plain = _budget(HouseholdLens(), 3)
    opted = _budget(HouseholdLens(frozenset({"Groceries"})), 3)
    plain_food = next(s for s in plain.group_statuses if s.group_id == FOOD.id)
    opted_food = next(s for s in opted.group_statuses if s.group_id == FOOD.id)
    extra = total_spending(
        HouseholdLens(frozenset({"Groceries"})),
        [tx for tx in ROWS if not tx.household and tx.category == "Groceries"],
    )
    assert opted_food.ytd_spent - plain_food.ytd_spent == extra == D("99.00")

    insights_food = next(
        g
        for g in compute_spending_trends(
            ROWS, LOOKUP, 2026, through_month=3, person_id=None
        ).group_summaries
        if g.group_id == FOOD.id
    )
    assert insights_food.ytd_total == plain_food.ytd_spent
    assert insights_food.ytd_total == opted_food.ytd_spent - extra


@pytest.mark.parametrize("lens", LENSES, ids=type)
def test_unmapped_category_lands_in_uncategorized_with_no_drift(
    lens: SpendingLens,
) -> None:
    budget = _budget(lens, 3)
    assert any(s.group_id is None for s in budget.group_statuses)
    assert budget.spending_drift is None
