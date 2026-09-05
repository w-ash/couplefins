from datetime import date
from decimal import Decimal
from uuid import UUID

from src.domain.budget import (
    BudgetOverviewInputs,
    _index_month_budgets,
    compute_average_monthly_spending,
    compute_budget_overview,
    determine_health,
)
from src.domain.constants import UNCATEGORIZED_GROUP_NAME
from src.domain.reconciliation import reconcile
from src.domain.spending_lens import HouseholdLens, PersonalLens, compute_breakdowns
from tests.fixtures.factories import (
    ALICE,
    BOB,
    make_category,
    make_category_group,
    make_category_group_budget,
    make_person,
    make_transaction,
)

# --- _index_month_budgets ---


def test_index_month_budgets_returns_match() -> None:
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    b = make_category_group_budget(group_id=gid, monthly_amount=Decimal(500))
    index = _index_month_budgets([b])
    assert gid in index
    assert index[gid].monthly_amount == Decimal(500)


def test_index_month_budgets_missing_group() -> None:
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    other = UUID("aaaaaaaa-0000-0000-0000-000000000002")
    b = make_category_group_budget(group_id=other)
    index = _index_month_budgets([b])
    assert gid not in index


def test_same_group_different_months_no_contamination() -> None:
    """Regression: per-month model must NOT cascade budgets across months."""
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    month1_budgets = [
        make_category_group_budget(
            group_id=gid, year=2026, month=1, monthly_amount=Decimal(500)
        ),
    ]
    month2_budgets: list = []

    assert gid in _index_month_budgets(month1_budgets)
    assert gid not in _index_month_budgets(month2_budgets)


# --- determine_health ---


def test_health_on_track() -> None:
    assert determine_health(Decimal(300), Decimal(500)) == "on_track"


def test_health_near_limit() -> None:
    assert determine_health(Decimal(400), Decimal(500)) == "near_limit"


def test_health_exactly_at_threshold() -> None:
    assert determine_health(Decimal(80), Decimal(100)) == "near_limit"


def test_health_over_budget() -> None:
    assert determine_health(Decimal(550), Decimal(500)) == "over_budget"


def test_health_exactly_at_budget() -> None:
    assert determine_health(Decimal(500), Decimal(500)) == "near_limit"


def test_health_zero_budget_no_spending() -> None:
    assert determine_health(Decimal(0), Decimal(0)) == "on_track"


def test_health_zero_budget_with_spending() -> None:
    assert determine_health(Decimal(10), Decimal(0)) == "over_budget"


# --- compute_average_monthly_spending ---


def test_average_spending_basic() -> None:
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    lookup = {"Groceries": (gid, "Food & Dining")}
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal(-100),
            date=date(2026, 1, 15),
            payer_person_id=UUID("bbbbbbbb-0000-0000-0000-000000000001"),
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal(-200),
            date=date(2026, 2, 15),
            payer_person_id=UUID("bbbbbbbb-0000-0000-0000-000000000001"),
        ),
    ]

    result = compute_average_monthly_spending(txs, lookup, through_month=2)
    assert result[gid] == Decimal(150)


def test_average_spending_no_data() -> None:
    result = compute_average_monthly_spending([], {}, through_month=3)
    assert result == {}


def test_average_spending_ignores_future_months() -> None:
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    lookup = {"Groceries": (gid, "Food & Dining")}
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal(-100),
            date=date(2026, 1, 15),
            payer_person_id=UUID("bbbbbbbb-0000-0000-0000-000000000001"),
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal(-300),
            date=date(2026, 3, 15),
            payer_person_id=UUID("bbbbbbbb-0000-0000-0000-000000000001"),
        ),
    ]

    result = compute_average_monthly_spending(txs, lookup, through_month=1)
    assert result[gid] == Decimal(100)


# --- compute_budget_overview ---


def test_overview_budgeted_groups_first() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    auto_gid = UUID("aaaaaaaa-0000-0000-0000-000000000002")
    payer = UUID("bbbbbbbb-0000-0000-0000-000000000001")

    groups = [
        make_category_group(id=food_gid, name="Food & Dining"),
        make_category_group(id=auto_gid, name="Auto & Transport"),
    ]
    month_budgets = [
        make_category_group_budget(
            group_id=food_gid,
            year=2026,
            month=1,
            monthly_amount=Decimal(500),
        ),
    ]
    year_budgets = list(month_budgets)
    lookup = {
        "Groceries": (food_gid, "Food & Dining"),
        "Gas": (auto_gid, "Auto & Transport"),
    }
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal(-200),
            date=date(2026, 1, 15),
            payer_person_id=payer,
        ),
        make_transaction(
            category="Gas",
            amount=Decimal(-50),
            date=date(2026, 1, 15),
            payer_person_id=payer,
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs(month_budgets, year_budgets, txs, lookup, groups, 2026, 1)
    )

    assert len(overview.group_statuses) == 2
    # Budgeted group first
    assert overview.group_statuses[0].group_name == "Food & Dining"
    assert overview.group_statuses[0].monthly_budget == Decimal(500)
    assert overview.group_statuses[0].monthly_health is not None
    # Unbudgeted group second
    assert overview.group_statuses[1].group_name == "Auto & Transport"
    assert overview.group_statuses[1].monthly_budget is None
    assert overview.group_statuses[1].monthly_health is None


def test_overview_grand_totals_exclude_unbudgeted() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    auto_gid = UUID("aaaaaaaa-0000-0000-0000-000000000002")
    payer = UUID("bbbbbbbb-0000-0000-0000-000000000001")

    groups = [
        make_category_group(id=food_gid, name="Food & Dining"),
        make_category_group(id=auto_gid, name="Auto & Transport"),
    ]
    month_budgets = [
        make_category_group_budget(
            group_id=food_gid,
            year=2026,
            month=1,
            monthly_amount=Decimal(500),
        ),
    ]
    year_budgets = list(month_budgets)
    lookup = {
        "Groceries": (food_gid, "Food & Dining"),
        "Gas": (auto_gid, "Auto & Transport"),
    }
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal(-200),
            date=date(2026, 1, 15),
            payer_person_id=payer,
        ),
        make_transaction(
            category="Gas",
            amount=Decimal(-50),
            date=date(2026, 1, 15),
            payer_person_id=payer,
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs(month_budgets, year_budgets, txs, lookup, groups, 2026, 1)
    )

    assert overview.total_monthly_budget == Decimal(500)
    assert overview.total_monthly_spent == Decimal(200)


def test_overview_unbudgeted_groups_without_spending_included() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    auto_gid = UUID("aaaaaaaa-0000-0000-0000-000000000002")

    groups = [
        make_category_group(id=food_gid, name="Food & Dining"),
        make_category_group(id=auto_gid, name="Auto & Transport"),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs([], [], [], {}, groups, 2026, 1)
    )

    assert len(overview.group_statuses) == 2
    assert all(s.monthly_budget is None for s in overview.group_statuses)
    assert all(s.monthly_spent == Decimal(0) for s in overview.group_statuses)


def test_overview_empty() -> None:
    overview = compute_budget_overview(
        BudgetOverviewInputs([], [], [], {}, [], 2026, 1)
    )

    assert overview.year == 2026
    assert overview.month == 1
    assert overview.group_statuses == []
    assert overview.total_monthly_budget == Decimal(0)
    assert overview.total_monthly_spent == Decimal(0)


def test_overview_ytd_computation() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    payer = UUID("bbbbbbbb-0000-0000-0000-000000000001")

    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    month_budgets = [
        make_category_group_budget(
            group_id=food_gid,
            year=2026,
            month=3,
            monthly_amount=Decimal(500),
        ),
    ]
    year_budgets = [
        make_category_group_budget(
            group_id=food_gid, year=2026, month=1, monthly_amount=Decimal(500)
        ),
        make_category_group_budget(
            group_id=food_gid, year=2026, month=2, monthly_amount=Decimal(500)
        ),
        make_category_group_budget(
            group_id=food_gid, year=2026, month=3, monthly_amount=Decimal(500)
        ),
    ]
    lookup = {"Groceries": (food_gid, "Food & Dining")}
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal(-200),
            date=date(2026, 1, 15),
            payer_person_id=payer,
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal(-300),
            date=date(2026, 2, 15),
            payer_person_id=payer,
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal(-150),
            date=date(2026, 3, 15),
            payer_person_id=payer,
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs(month_budgets, year_budgets, txs, lookup, groups, 2026, 3)
    )

    status = overview.group_statuses[0]
    assert status.monthly_spent == Decimal(150)
    assert status.ytd_spent == Decimal(650)
    assert status.ytd_budget == Decimal(1500)
    assert status.monthly_health == "on_track"
    assert overview.total_ytd_budget == Decimal(1500)
    assert overview.total_ytd_spent == Decimal(650)


def test_ytd_categories_include_earlier_month_only_categories() -> None:
    """YTD categories must show categories with earlier-month spend even
    when the viewed month has none — the monthly `categories` list doesn't."""
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    payer = UUID("bbbbbbbb-0000-0000-0000-000000000001")

    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    lookup = {
        "Groceries": (food_gid, "Food & Dining"),
        "Coffee": (food_gid, "Food & Dining"),
    }
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal("-100.00"),
            date=date(2026, 3, 10),
            payer_person_id=payer,
        ),
        # Coffee was only spent in January — absent from March entirely.
        make_transaction(
            category="Coffee",
            amount=Decimal("-20.00"),
            date=date(2026, 1, 5),
            payer_person_id=payer,
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs([], [], txs, lookup, groups, 2026, 3)
    )
    status = overview.group_statuses[0]

    monthly_cats = {c.category for c in status.categories}
    ytd_cats = {c.category for c in status.ytd_categories}
    assert monthly_cats == {"Groceries"}
    assert ytd_cats == {"Groceries", "Coffee"}

    coffee_ytd = next(c for c in status.ytd_categories if c.category == "Coffee")
    assert coffee_ytd.total_amount == Decimal("20.00")


def test_ytd_totals_include_group_unbudgeted_in_viewed_month() -> None:
    """A group budgeted Jan-Feb but not the viewed March still contributes
    its YTD budget/spend to the grand totals — otherwise its own row would
    outrun the Total (US-BUDGET-3)."""
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    payer = UUID("bbbbbbbb-0000-0000-0000-000000000001")

    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    year_budgets = [
        make_category_group_budget(
            group_id=food_gid, year=2026, month=1, monthly_amount=Decimal(300)
        ),
        make_category_group_budget(
            group_id=food_gid, year=2026, month=2, monthly_amount=Decimal(300)
        ),
    ]
    month_budgets: list = []  # No budget for March, the viewed month.
    lookup = {"Groceries": (food_gid, "Food & Dining")}
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal("-100.00"),
            date=date(2026, 1, 15),
            payer_person_id=payer,
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal("-50.00"),
            date=date(2026, 2, 10),
            payer_person_id=payer,
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs(month_budgets, year_budgets, txs, lookup, groups, 2026, 3)
    )

    status = overview.group_statuses[0]
    assert status.monthly_budget is None
    assert status.ytd_budget == Decimal(600)
    assert status.ytd_spent == Decimal("150.00")
    # Visible rows must sum to the Total stat.
    assert overview.total_ytd_budget == Decimal(600)
    assert overview.total_ytd_spent == Decimal("150.00")


def test_uncategorized_row_surfaces_unmapped_spending() -> None:
    """Spending in a category with no group mapping gets its own
    Uncategorized status instead of vanishing from every status and total."""
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    payer = UUID("bbbbbbbb-0000-0000-0000-000000000001")

    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    # "Mystery Category" is intentionally absent from the lookup.
    lookup = {"Groceries": (food_gid, "Food & Dining")}
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal("-100.00"),
            household=True,
            date=date(2026, 1, 10),
            payer_person_id=payer,
        ),
        make_transaction(
            category="Mystery Category",
            amount=Decimal("-40.00"),
            household=True,
            date=date(2026, 1, 12),
            payer_person_id=payer,
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs([], [], txs, lookup, groups, 2026, 1)
    )

    uncategorized = next(
        s for s in overview.group_statuses if s.group_name == UNCATEGORIZED_GROUP_NAME
    )
    assert uncategorized.group_id is None
    assert uncategorized.monthly_budget is None
    assert uncategorized.monthly_spent == Decimal("40.00")
    # Item 3's "any group with YTD spend" rule now folds it into the total —
    # dollars no longer vanish.
    assert overview.total_ytd_spent == Decimal("140.00")
    # Everything is accounted for: the drift check finds nothing amiss.
    assert overview.spending_drift is None


def test_no_uncategorized_row_when_everything_is_mapped() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    lookup = {"Groceries": (food_gid, "Food & Dining")}
    txs = [
        make_transaction(category="Groceries", amount=Decimal("-100.00")),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs([], [], txs, lookup, groups, 2026, 1)
    )

    assert all(
        s.group_name != UNCATEGORIZED_GROUP_NAME for s in overview.group_statuses
    )


def test_personal_overview_uncategorized_row_surfaces() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    lookup: dict[str, tuple[UUID, str]] = {}  # nothing mapped

    txs = [
        make_transaction(
            category="Mystery Category",
            amount=Decimal("-40.00"),
            household=False,
            payer_percentage=100,
            payer_person_id=ALICE.id,
            date=date(2026, 1, 12),
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs([], [], txs, lookup, groups, 2026, 1),
        PersonalLens(ALICE.id),
    )

    uncategorized = next(
        s for s in overview.group_statuses if s.group_name == UNCATEGORIZED_GROUP_NAME
    )
    assert uncategorized.group_id is None
    assert uncategorized.personal_spending == Decimal("40.00")
    assert uncategorized.monthly_spent == Decimal("40.00")


def test_excluded_transaction_not_budget_relevant() -> None:
    tx = make_transaction(household=True, is_excluded=True)
    assert HouseholdLens(frozenset()).is_relevant(tx) is False


def test_excluded_transaction_not_budget_relevant_even_with_personal_category() -> None:
    tx = make_transaction(category="Groceries", household=False, is_excluded=True)
    assert HouseholdLens(frozenset({"Groceries"})).is_relevant(tx) is False


def test_settlement_transaction_not_budget_relevant() -> None:
    tx = make_transaction(household=True, is_settlement=True)
    assert HouseholdLens(frozenset()).is_relevant(tx) is False


def test_settlement_transaction_not_budget_relevant_even_with_personal_category() -> (
    None
):
    tx = make_transaction(category="Groceries", household=False, is_settlement=True)
    assert HouseholdLens(frozenset({"Groceries"})).is_relevant(tx) is False


# --- category breakdown per-source tracking ---


def test_breakdown_splits_household_vs_personal() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    alice = UUID("bbbbbbbb-0000-0000-0000-000000000001")
    bob = UUID("bbbbbbbb-0000-0000-0000-000000000002")

    lookup = {"Groceries": (food_gid, "Food & Dining")}
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal(-100),
            household=True,
            payer_person_id=alice,
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal(-60),
            household=False,
            payer_person_id=alice,
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal(-40),
            household=False,
            payer_person_id=bob,
        ),
    ]

    groups = compute_breakdowns(HouseholdLens({"Groceries"}), txs, lookup)
    assert len(groups) == 1
    cat = groups[0].categories[0]

    assert cat.total_amount == Decimal(200)
    assert cat.household_amount == Decimal(100)
    assert cat.personal_amounts[alice] == Decimal(60)
    assert cat.personal_amounts[bob] == Decimal(40)


def test_breakdown_no_personal_categories_all_household() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    alice = UUID("bbbbbbbb-0000-0000-0000-000000000001")

    lookup = {"Groceries": (food_gid, "Food & Dining")}
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal(-100),
            household=True,
            payer_person_id=alice,
        ),
    ]

    groups = compute_breakdowns(HouseholdLens(), txs, lookup)
    cat = groups[0].categories[0]

    assert cat.total_amount == Decimal(100)
    assert cat.household_amount == Decimal(100)
    assert cat.personal_amounts == {}


def test_breakdown_personal_not_in_set_is_not_household_spending() -> None:
    """A personal row whose category is not opted in is outside the
    household lens entirely — the accumulator selects rows itself."""
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    alice = UUID("bbbbbbbb-0000-0000-0000-000000000001")

    lookup = {"Groceries": (food_gid, "Food & Dining")}
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal(-50),
            household=False,
            payer_person_id=alice,
        ),
    ]

    assert compute_breakdowns(HouseholdLens(), txs, lookup) == []


def test_breakdown_refund_nets_instead_of_inflating() -> None:
    """-$200 expense + $60 refund must net to $140 spent, not $260."""
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    alice = UUID("bbbbbbbb-0000-0000-0000-000000000001")

    lookup = {"Groceries": (food_gid, "Food & Dining")}
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal("-200.00"),
            household=True,
            payer_person_id=alice,
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal("60.00"),
            household=True,
            payer_person_id=alice,
        ),
    ]

    groups = compute_breakdowns(HouseholdLens(), txs, lookup)
    cat = groups[0].categories[0]

    assert cat.total_amount == Decimal("140.00")
    assert cat.household_amount == Decimal("140.00")


def test_overview_refund_flips_health_off_over_budget() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    payer = UUID("bbbbbbbb-0000-0000-0000-000000000001")

    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    month_budgets = [
        make_category_group_budget(
            group_id=food_gid, year=2026, month=1, monthly_amount=Decimal(200)
        ),
    ]
    year_budgets = list(month_budgets)
    lookup = {"Groceries": (food_gid, "Food & Dining")}
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal("-250.00"),
            household=True,
            payer_person_id=payer,
            date=date(2026, 1, 5),
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal("100.00"),
            household=True,
            payer_person_id=payer,
            date=date(2026, 1, 10),
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs(month_budgets, year_budgets, txs, lookup, groups, 2026, 1)
    )
    status = overview.group_statuses[0]

    # Without the refund, $250 spent against a $200 budget would be over_budget.
    assert status.monthly_spent == Decimal("150.00")
    assert status.monthly_health == "on_track"


def test_household_split_spending_matches_reconcile_net() -> None:
    """Property: for household split-only inputs, the budget's household
    group total must equal reconcile()'s net_household_spending — the same
    underlying money, aggregated two different ways."""
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    group = make_category_group(id=food_gid, name="Food & Dining")
    category = make_category(name="Groceries", group_id=food_gid)
    lookup = {"Groceries": (food_gid, "Food & Dining")}

    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal("-200.00"),
            payer_percentage=50,
            household=True,
            payer_person_id=alice.id,
            date=date(2026, 1, 5),
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal("60.00"),
            payer_percentage=50,
            household=True,
            payer_person_id=alice.id,
            date=date(2026, 1, 10),
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal("-150.00"),
            payer_percentage=70,
            household=True,
            payer_person_id=bob.id,
            date=date(2026, 1, 12),
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal("-40.00"),
            payer_percentage=30,
            household=True,
            payer_person_id=alice.id,
            date=date(2026, 1, 20),
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs([], [], txs, lookup, [group], 2026, 1)
    )
    summary = reconcile(
        txs,
        [alice, bob],
        [category],
        [group],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert overview.group_statuses[0].monthly_spent == summary.net_household_spending


# --- compute_budget_overview with PersonalLens ---


def test_personal_overview_mixed_household_and_personal() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    month_budgets = [
        make_category_group_budget(
            group_id=food_gid,
            year=2026,
            month=1,
            monthly_amount=Decimal(400),
            person_id=ALICE.id,
        ),
    ]
    year_budgets = list(month_budgets)
    lookup = {"Groceries": (food_gid, "Food & Dining")}

    txs = [
        # Shared 50/50 paid by Alice: Alice's share = $50
        make_transaction(
            category="Groceries",
            amount=Decimal(-100),
            payer_percentage=50,
            household=True,
            payer_person_id=ALICE.id,
            date=date(2026, 1, 10),
        ),
        # Shared 50/50 paid by Bob: Alice's share = $30
        make_transaction(
            category="Groceries",
            amount=Decimal(-60),
            payer_percentage=50,
            household=True,
            payer_person_id=BOB.id,
            date=date(2026, 1, 12),
        ),
        # Alice's personal grocery run: $40
        make_transaction(
            category="Groceries",
            amount=Decimal(-40),
            payer_percentage=100,
            household=False,
            payer_person_id=ALICE.id,
            date=date(2026, 1, 15),
        ),
        # Bob's personal (should not appear for Alice)
        make_transaction(
            category="Groceries",
            amount=Decimal(-25),
            payer_percentage=100,
            household=False,
            payer_person_id=BOB.id,
            date=date(2026, 1, 16),
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs(month_budgets, year_budgets, txs, lookup, groups, 2026, 1),
        PersonalLens(ALICE.id),
    )

    assert len(overview.group_statuses) == 1
    status = overview.group_statuses[0]
    # shared: $50 (Alice pays 100 @ 50%) + $30 (Bob pays 60 @ 50%) = $80
    assert status.household_spending == Decimal("80.00")
    # personal: $40 (Alice's own tx)
    assert status.personal_spending == Decimal("40.00")
    # total = $120
    assert status.monthly_spent == Decimal("120.00")
    assert status.monthly_budget == Decimal(400)
    assert status.monthly_health == "on_track"


def test_personal_overview_empty_txs() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]

    overview = compute_budget_overview(
        BudgetOverviewInputs([], [], [], {}, groups, 2026, 1), PersonalLens(ALICE.id)
    )

    assert len(overview.group_statuses) == 1
    assert overview.group_statuses[0].monthly_spent == Decimal(0)
    assert overview.total_monthly_spent == Decimal(0)


def test_personal_overview_excludes_excluded_txs() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    lookup = {"Groceries": (food_gid, "Food & Dining")}

    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal(-100),
            household=True,
            payer_person_id=ALICE.id,
            is_excluded=True,
            date=date(2026, 1, 10),
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs([], [], txs, lookup, groups, 2026, 1),
        PersonalLens(ALICE.id),
    )
    assert len(overview.group_statuses) == 1
    assert overview.group_statuses[0].monthly_spent == Decimal(0)


def test_personal_overview_partner_household_creates_share() -> None:
    """Alice should have a share of Bob's household payments."""
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    month_budgets = [
        make_category_group_budget(
            group_id=food_gid,
            year=2026,
            month=1,
            monthly_amount=Decimal(500),
            person_id=ALICE.id,
        ),
    ]
    year_budgets = list(month_budgets)
    lookup = {"Groceries": (food_gid, "Food & Dining")}

    txs = [
        # Bob pays $200 shared 50/50: Alice's share = $100
        make_transaction(
            category="Groceries",
            amount=Decimal(-200),
            payer_percentage=50,
            household=True,
            payer_person_id=BOB.id,
            date=date(2026, 1, 10),
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs(month_budgets, year_budgets, txs, lookup, groups, 2026, 1),
        PersonalLens(ALICE.id),
    )

    status = overview.group_statuses[0]
    assert status.household_spending == Decimal("100.00")
    assert status.personal_spending == Decimal(0)
    assert status.monthly_spent == Decimal("100.00")


def test_personal_overview_spotted_front_attributes_to_beneficiary() -> None:
    """A spotted front ($200 tagged bob, pct=0, payer=Alice) is $0 for Alice,
    $200 for Bob — the beneficiary's personal spending (decided 2026-07-02)."""
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    lookup = {"Groceries": (food_gid, "Food & Dining")}

    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal("-200.00"),
            payer_percentage=0,
            household=False,
            payer_person_id=ALICE.id,
            tags=("bob",),
            date=date(2026, 1, 10),
        ),
    ]

    alice_overview = compute_budget_overview(
        BudgetOverviewInputs([], [], txs, lookup, groups, 2026, 1),
        PersonalLens(ALICE.id),
    )
    bob_overview = compute_budget_overview(
        BudgetOverviewInputs([], [], txs, lookup, groups, 2026, 1), PersonalLens(BOB.id)
    )

    # Alice (payer, 0% share) sees nothing.
    alice_status = alice_overview.group_statuses[0]
    assert alice_status.personal_spending == Decimal(0)
    assert alice_status.monthly_spent == Decimal(0)
    # Bob (beneficiary, 100% share) sees the full $200.
    bob_status = bob_overview.group_statuses[0]
    assert bob_status.personal_spending == Decimal("200.00")
    assert bob_status.monthly_spent == Decimal("200.00")


def test_personal_overview_personal_split_divides_across_both() -> None:
    """A non-household 70/30 split books 70% to the payer, 30% to the
    beneficiary — both are relevant, each sees their own share."""
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    lookup = {"Groceries": (food_gid, "Food & Dining")}

    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal("-100.00"),
            payer_percentage=70,
            household=False,
            payer_person_id=ALICE.id,
            date=date(2026, 1, 10),
        ),
    ]

    alice_overview = compute_budget_overview(
        BudgetOverviewInputs([], [], txs, lookup, groups, 2026, 1),
        PersonalLens(ALICE.id),
    )
    bob_overview = compute_budget_overview(
        BudgetOverviewInputs([], [], txs, lookup, groups, 2026, 1), PersonalLens(BOB.id)
    )

    assert alice_overview.group_statuses[0].personal_spending == Decimal("70.00")
    assert bob_overview.group_statuses[0].personal_spending == Decimal("30.00")


def test_personal_overview_household_refund_reduces_share() -> None:
    """A refund on a household split must reduce Alice's share, not inflate it."""
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    lookup = {"Groceries": (food_gid, "Food & Dining")}

    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal("-200.00"),
            payer_percentage=50,
            household=True,
            payer_person_id=ALICE.id,
            date=date(2026, 1, 5),
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal("60.00"),
            payer_percentage=50,
            household=True,
            payer_person_id=ALICE.id,
            date=date(2026, 1, 10),
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs([], [], txs, lookup, groups, 2026, 1),
        PersonalLens(ALICE.id),
    )
    status = overview.group_statuses[0]

    # Alice's share: $100 expense share - $30 refund share = $70
    assert status.household_spending == Decimal("70.00")
    assert status.monthly_spent == Decimal("70.00")


def test_personal_overview_ytd_across_months() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    month_budgets = [
        make_category_group_budget(
            group_id=food_gid,
            year=2026,
            month=2,
            monthly_amount=Decimal(300),
            person_id=ALICE.id,
        ),
    ]
    year_budgets = [
        make_category_group_budget(
            group_id=food_gid,
            year=2026,
            month=1,
            monthly_amount=Decimal(300),
            person_id=ALICE.id,
        ),
        make_category_group_budget(
            group_id=food_gid,
            year=2026,
            month=2,
            monthly_amount=Decimal(300),
            person_id=ALICE.id,
        ),
    ]
    lookup = {"Groceries": (food_gid, "Food & Dining")}

    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal(-100),
            payer_percentage=50,
            household=True,
            payer_person_id=ALICE.id,
            date=date(2026, 1, 15),
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal(-80),
            payer_percentage=100,
            household=False,
            payer_person_id=ALICE.id,
            date=date(2026, 2, 15),
        ),
    ]

    overview = compute_budget_overview(
        BudgetOverviewInputs(month_budgets, year_budgets, txs, lookup, groups, 2026, 2),
        PersonalLens(ALICE.id),
    )

    status = overview.group_statuses[0]
    # Monthly (Feb): personal $80
    assert status.monthly_spent == Decimal("80.00")
    # YTD (Jan+Feb): $50 (Jan shared) + $80 (Feb personal) = $130
    assert status.ytd_spent == Decimal("130.00")
    assert status.ytd_budget == Decimal(600)


# --- transfer groups ---


def test_transfer_group_gets_no_status_row_in_either_overview() -> None:
    """A transfer group is money movement: no row, no budget, and the
    integrity check stays clean even if a transfer row reaches the domain."""
    food = make_category_group(name="Food & Dining")
    transfer = make_category_group(name="Transfer", kind="transfer")
    lookup = {
        "Dining Out": (food.id, food.name),
        "Credit Card Payment": (transfer.id, transfer.name),
    }
    txs = [
        make_transaction(
            date=date(2026, 1, 5),
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=ALICE.id,
        ),
        make_transaction(
            date=date(2026, 1, 6),
            category="Credit Card Payment",
            amount=Decimal("-900.00"),
            payer_person_id=ALICE.id,
        ),
    ]
    inputs = BudgetOverviewInputs([], [], txs, lookup, [food, transfer], 2026, 1)

    household = compute_budget_overview(inputs)
    personal = compute_budget_overview(inputs, PersonalLens(ALICE.id))

    for overview in (household, personal):
        assert [s.group_name for s in overview.group_statuses] == ["Food & Dining"]
        assert overview.spending_drift is None
    assert household.total_ytd_spent == Decimal("100.00")
    assert personal.total_ytd_spent == Decimal("50.00")


# --- one lens for everyone ---


def test_personal_overview_partner_paid_household_row_is_household_only() -> None:
    """Both partners buy their own concert ticket and tag it household: the
    household view shows both; each personal view shows only its own."""
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    lookup = {"Concerts": (food_gid, "Food & Dining")}
    txs = [
        make_transaction(
            category="Concerts",
            amount=Decimal("-60.00"),
            household=True,
            payer_percentage=100,
            payer_person_id=ALICE.id,
        ),
        make_transaction(
            category="Concerts",
            amount=Decimal("-45.00"),
            household=True,
            payer_percentage=100,
            payer_person_id=BOB.id,
        ),
    ]
    inputs = BudgetOverviewInputs([], [], txs, lookup, groups, 2026, 1)

    household = compute_budget_overview(inputs)
    alice = compute_budget_overview(inputs, PersonalLens(ALICE.id))
    bob = compute_budget_overview(inputs, PersonalLens(BOB.id))

    assert household.group_statuses[0].monthly_spent == Decimal("105.00")
    assert alice.group_statuses[0].monthly_spent == Decimal("60.00")
    assert alice.group_statuses[0].categories[0].transaction_count == 1
    assert bob.group_statuses[0].monthly_spent == Decimal("45.00")
    assert bob.group_statuses[0].categories[0].transaction_count == 1


def test_personal_overview_spotted_payer_gets_no_zero_row() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    lookup = {"Dining Out": (food_gid, "Food & Dining")}
    txs = [
        make_transaction(
            category="Dining Out",
            amount=Decimal("-30.00"),
            household=False,
            payer_percentage=0,
            payer_person_id=ALICE.id,
            tags=("bob",),
        )
    ]
    inputs = BudgetOverviewInputs([], [], txs, lookup, groups, 2026, 1)

    alice = compute_budget_overview(inputs, PersonalLens(ALICE.id))
    bob = compute_budget_overview(inputs, PersonalLens(BOB.id))

    assert alice.group_statuses[0].categories == []
    assert alice.group_statuses[0].monthly_spent == Decimal(0)
    assert bob.group_statuses[0].monthly_spent == Decimal("30.00")


def test_average_monthly_spending_nets_refunds() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    lookup = {"Groceries": (food_gid, "Food & Dining")}
    txs = [
        make_transaction(
            date=date(2026, 1, 5),
            category="Groceries",
            amount=Decimal("-200.00"),
            payer_person_id=ALICE.id,
        ),
        make_transaction(
            date=date(2026, 1, 9),
            category="Groceries",
            amount=Decimal("50.00"),
            payer_person_id=ALICE.id,
        ),
        make_transaction(
            date=date(2026, 2, 5),
            category="Groceries",
            amount=Decimal("-100.00"),
            payer_person_id=ALICE.id,
        ),
    ]

    assert compute_average_monthly_spending(txs, lookup, through_month=2) == {
        food_gid: Decimal("125.00")
    }
    assert compute_average_monthly_spending(
        txs, lookup, through_month=2, lens=PersonalLens(ALICE.id)
    ) == {food_gid: Decimal("62.50")}


def test_average_divisor_counts_months_with_any_row_under_the_lens() -> None:
    """A refund-only month is a month of activity: Jan -200, Feb +50 →
    150 / 2 = 75. A month with no rows would not count."""
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    lookup = {"Groceries": (food_gid, "Food & Dining")}
    txs = [
        make_transaction(
            date=date(2026, 1, 5),
            category="Groceries",
            amount=Decimal("-200.00"),
            payer_person_id=ALICE.id,
        ),
        make_transaction(
            date=date(2026, 2, 9),
            category="Groceries",
            amount=Decimal("50.00"),
            payer_person_id=ALICE.id,
        ),
    ]

    assert compute_average_monthly_spending(txs, lookup, through_month=2) == {
        food_gid: Decimal("75.00")
    }
    # through_month=1 excludes February entirely: 200 / 1.
    assert compute_average_monthly_spending(txs, lookup, through_month=1) == {
        food_gid: Decimal("200.00")
    }
