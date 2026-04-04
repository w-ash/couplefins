from datetime import date
from decimal import Decimal
from uuid import UUID

from src.domain.budget import (
    _compute_ytd_budget,
    _index_month_budgets,
    _is_budget_relevant,
    _is_personal_budget_relevant,
    compute_average_monthly_spending,
    compute_budget_overview,
    compute_person_share,
    compute_personal_budget_overview,
    determine_health,
)
from src.domain.categories import compute_category_breakdowns
from tests.fixtures.factories import (
    make_category_group,
    make_category_group_budget,
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


# --- _compute_ytd_budget ---


def test_ytd_sums_monthly_amounts() -> None:
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    budgets = [
        make_category_group_budget(
            group_id=gid, year=2026, month=1, monthly_amount=Decimal(500)
        ),
        make_category_group_budget(
            group_id=gid, year=2026, month=2, monthly_amount=Decimal(500)
        ),
        make_category_group_budget(
            group_id=gid, year=2026, month=3, monthly_amount=Decimal(600)
        ),
    ]
    result = _compute_ytd_budget(budgets, gid, 3)
    assert result == Decimal(1600)


def test_ytd_with_gap_month_contributes_zero() -> None:
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    budgets = [
        make_category_group_budget(
            group_id=gid, year=2026, month=1, monthly_amount=Decimal(500)
        ),
        make_category_group_budget(
            group_id=gid, year=2026, month=3, monthly_amount=Decimal(600)
        ),
    ]
    # Month 2 has no budget, contributes $0
    result = _compute_ytd_budget(budgets, gid, 3)
    assert result == Decimal(1100)


def test_ytd_no_budgets_returns_none() -> None:
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    result = _compute_ytd_budget([], gid, 6)
    assert result is None


def test_ytd_excludes_future_months() -> None:
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    budgets = [
        make_category_group_budget(
            group_id=gid, year=2026, month=1, monthly_amount=Decimal(500)
        ),
        make_category_group_budget(
            group_id=gid, year=2026, month=4, monthly_amount=Decimal(700)
        ),
    ]
    result = _compute_ytd_budget(budgets, gid, 2)
    assert result == Decimal(500)


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
        month_budgets, year_budgets, txs, lookup, groups, 2026, 1
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
        month_budgets, year_budgets, txs, lookup, groups, 2026, 1
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

    overview = compute_budget_overview([], [], [], {}, groups, 2026, 1)

    assert len(overview.group_statuses) == 2
    assert all(s.monthly_budget is None for s in overview.group_statuses)
    assert all(s.monthly_spent == Decimal(0) for s in overview.group_statuses)


def test_overview_empty() -> None:
    overview = compute_budget_overview([], [], [], {}, [], 2026, 1)

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
        month_budgets, year_budgets, txs, lookup, groups, 2026, 3
    )

    status = overview.group_statuses[0]
    assert status.monthly_spent == Decimal(150)
    assert status.ytd_spent == Decimal(650)
    assert status.ytd_budget == Decimal(1500)
    assert status.monthly_health == "on_track"
    assert overview.total_ytd_budget == Decimal(1500)
    assert overview.total_ytd_spent == Decimal(650)


def test_excluded_transaction_not_budget_relevant() -> None:
    tx = make_transaction(household=True, is_excluded=True)
    assert _is_budget_relevant(tx, frozenset()) is False


def test_excluded_transaction_not_budget_relevant_even_with_personal_category() -> None:
    tx = make_transaction(category="Groceries", household=False, is_excluded=True)
    assert _is_budget_relevant(tx, frozenset({"Groceries"})) is False


def test_settlement_transaction_not_budget_relevant() -> None:
    tx = make_transaction(household=True, is_settlement=True)
    assert _is_budget_relevant(tx, frozenset()) is False


def test_settlement_transaction_not_budget_relevant_even_with_personal_category() -> (
    None
):
    tx = make_transaction(category="Groceries", household=False, is_settlement=True)
    assert _is_budget_relevant(tx, frozenset({"Groceries"})) is False


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

    groups = compute_category_breakdowns(txs, lookup, personal_categories={"Groceries"})
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

    groups = compute_category_breakdowns(txs, lookup)
    cat = groups[0].categories[0]

    assert cat.total_amount == Decimal(100)
    assert cat.household_amount == Decimal(100)
    assert cat.personal_amounts == {}


def test_breakdown_personal_not_in_set_excluded_from_personal_amounts() -> None:
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

    # "Groceries" not in personal_categories, so personal_amounts stays empty
    groups = compute_category_breakdowns(txs, lookup, personal_categories=frozenset())
    cat = groups[0].categories[0]

    assert cat.total_amount == Decimal(50)
    assert cat.household_amount == Decimal(0)
    assert cat.personal_amounts == {}


# --- compute_person_share ---

ALICE = UUID("bbbbbbbb-0000-0000-0000-000000000001")
BOB = UUID("bbbbbbbb-0000-0000-0000-000000000002")


def test_person_share_payer_household_50_50() -> None:
    tx = make_transaction(
        amount=Decimal(-100), payer_percentage=50, payer_person_id=ALICE
    )
    assert compute_person_share(tx, ALICE) == Decimal("50.00")


def test_person_share_non_payer_household_50_50() -> None:
    tx = make_transaction(
        amount=Decimal(-100), payer_percentage=50, payer_person_id=ALICE
    )
    assert compute_person_share(tx, BOB) == Decimal("50.00")


def test_person_share_payer_custom_split() -> None:
    tx = make_transaction(
        amount=Decimal(-200), payer_percentage=70, payer_person_id=ALICE
    )
    assert compute_person_share(tx, ALICE) == Decimal("140.00")


def test_person_share_non_payer_custom_split() -> None:
    tx = make_transaction(
        amount=Decimal(-200), payer_percentage=70, payer_person_id=ALICE
    )
    assert compute_person_share(tx, BOB) == Decimal("60.00")


def test_person_share_spotted_payer() -> None:
    tx = make_transaction(
        amount=Decimal(-30), payer_percentage=0, payer_person_id=ALICE
    )
    assert compute_person_share(tx, ALICE) == Decimal("0.00")


def test_person_share_spotted_beneficiary() -> None:
    tx = make_transaction(
        amount=Decimal(-30), payer_percentage=0, payer_person_id=ALICE
    )
    assert compute_person_share(tx, BOB) == Decimal("30.00")


def test_person_share_household_no_split_payer() -> None:
    tx = make_transaction(
        amount=Decimal(-60), payer_percentage=100, payer_person_id=ALICE
    )
    assert compute_person_share(tx, ALICE) == Decimal("60.00")


def test_person_share_household_no_split_non_payer() -> None:
    tx = make_transaction(
        amount=Decimal(-60), payer_percentage=100, payer_person_id=ALICE
    )
    assert compute_person_share(tx, BOB) == Decimal("0.00")


# --- _is_personal_budget_relevant ---


def test_personal_relevant_household_tx() -> None:
    tx = make_transaction(household=True, payer_person_id=ALICE)
    assert _is_personal_budget_relevant(tx, BOB) is True


def test_personal_relevant_own_personal_tx() -> None:
    tx = make_transaction(household=False, payer_person_id=ALICE)
    assert _is_personal_budget_relevant(tx, ALICE) is True


def test_personal_irrelevant_other_personal_tx() -> None:
    tx = make_transaction(household=False, payer_person_id=ALICE)
    assert _is_personal_budget_relevant(tx, BOB) is False


def test_personal_irrelevant_excluded() -> None:
    tx = make_transaction(household=True, is_excluded=True)
    assert _is_personal_budget_relevant(tx, ALICE) is False


def test_personal_irrelevant_settlement() -> None:
    tx = make_transaction(household=True, is_settlement=True)
    assert _is_personal_budget_relevant(tx, ALICE) is False


# --- compute_personal_budget_overview ---


def test_personal_overview_mixed_household_and_personal() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    month_budgets = [
        make_category_group_budget(
            group_id=food_gid,
            year=2026,
            month=1,
            monthly_amount=Decimal(400),
            person_id=ALICE,
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
            payer_person_id=ALICE,
            date=date(2026, 1, 10),
        ),
        # Shared 50/50 paid by Bob: Alice's share = $30
        make_transaction(
            category="Groceries",
            amount=Decimal(-60),
            payer_percentage=50,
            household=True,
            payer_person_id=BOB,
            date=date(2026, 1, 12),
        ),
        # Alice's personal grocery run: $40
        make_transaction(
            category="Groceries",
            amount=Decimal(-40),
            payer_percentage=100,
            household=False,
            payer_person_id=ALICE,
            date=date(2026, 1, 15),
        ),
        # Bob's personal (should not appear for Alice)
        make_transaction(
            category="Groceries",
            amount=Decimal(-25),
            payer_percentage=100,
            household=False,
            payer_person_id=BOB,
            date=date(2026, 1, 16),
        ),
    ]

    overview = compute_personal_budget_overview(
        month_budgets, year_budgets, txs, lookup, groups, 2026, 1, ALICE
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

    overview = compute_personal_budget_overview([], [], [], {}, groups, 2026, 1, ALICE)

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
            payer_person_id=ALICE,
            is_excluded=True,
            date=date(2026, 1, 10),
        ),
    ]

    overview = compute_personal_budget_overview(
        [], [], txs, lookup, groups, 2026, 1, ALICE
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
            person_id=ALICE,
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
            payer_person_id=BOB,
            date=date(2026, 1, 10),
        ),
    ]

    overview = compute_personal_budget_overview(
        month_budgets, year_budgets, txs, lookup, groups, 2026, 1, ALICE
    )

    status = overview.group_statuses[0]
    assert status.household_spending == Decimal("100.00")
    assert status.personal_spending == Decimal(0)
    assert status.monthly_spent == Decimal("100.00")


def test_personal_overview_ytd_across_months() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    month_budgets = [
        make_category_group_budget(
            group_id=food_gid,
            year=2026,
            month=2,
            monthly_amount=Decimal(300),
            person_id=ALICE,
        ),
    ]
    year_budgets = [
        make_category_group_budget(
            group_id=food_gid,
            year=2026,
            month=1,
            monthly_amount=Decimal(300),
            person_id=ALICE,
        ),
        make_category_group_budget(
            group_id=food_gid,
            year=2026,
            month=2,
            monthly_amount=Decimal(300),
            person_id=ALICE,
        ),
    ]
    lookup = {"Groceries": (food_gid, "Food & Dining")}

    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal(-100),
            payer_percentage=50,
            household=True,
            payer_person_id=ALICE,
            date=date(2026, 1, 15),
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal(-80),
            payer_percentage=100,
            household=False,
            payer_person_id=ALICE,
            date=date(2026, 2, 15),
        ),
    ]

    overview = compute_personal_budget_overview(
        month_budgets, year_budgets, txs, lookup, groups, 2026, 2, ALICE
    )

    status = overview.group_statuses[0]
    # Monthly (Feb): personal $80
    assert status.monthly_spent == Decimal("80.00")
    # YTD (Jan+Feb): $50 (Jan shared) + $80 (Feb personal) = $130
    assert status.ytd_spent == Decimal("130.00")
    assert status.ytd_budget == Decimal(600)
