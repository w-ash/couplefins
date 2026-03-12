from datetime import date
from decimal import Decimal
from uuid import UUID

from src.domain.budget import (
    compute_average_monthly_spending,
    compute_budget_overview,
    compute_ytd_budget,
    determine_health,
    resolve_effective_budget,
)
from tests.fixtures.factories import (
    make_category_group,
    make_category_group_budget,
    make_transaction,
)

# --- resolve_effective_budget ---


def test_resolve_picks_most_recent_before_target() -> None:
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    b1 = make_category_group_budget(
        group_id=gid, effective_from=date(2026, 1, 1), monthly_amount=Decimal(500)
    )
    b2 = make_category_group_budget(
        group_id=gid, effective_from=date(2026, 3, 1), monthly_amount=Decimal(600)
    )
    b3 = make_category_group_budget(
        group_id=gid, effective_from=date(2026, 6, 1), monthly_amount=Decimal(700)
    )

    result = resolve_effective_budget([b1, b2, b3], date(2026, 4, 1))
    assert result is not None
    assert result.monthly_amount == Decimal(600)


def test_resolve_returns_none_when_no_budget_applicable() -> None:
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    b = make_category_group_budget(group_id=gid, effective_from=date(2026, 6, 1))

    result = resolve_effective_budget([b], date(2026, 1, 1))
    assert result is None


def test_resolve_returns_exact_match() -> None:
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    b = make_category_group_budget(
        group_id=gid, effective_from=date(2026, 3, 1), monthly_amount=Decimal(500)
    )

    result = resolve_effective_budget([b], date(2026, 3, 1))
    assert result is not None
    assert result.monthly_amount == Decimal(500)


# --- compute_ytd_budget ---


def test_ytd_single_rate() -> None:
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    b = make_category_group_budget(
        group_id=gid, effective_from=date(2026, 1, 1), monthly_amount=Decimal(500)
    )

    result = compute_ytd_budget([b], 2026, 3)
    assert result == Decimal(1500)


def test_ytd_with_mid_year_change() -> None:
    gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    b1 = make_category_group_budget(
        group_id=gid, effective_from=date(2026, 1, 1), monthly_amount=Decimal(500)
    )
    b2 = make_category_group_budget(
        group_id=gid, effective_from=date(2026, 3, 1), monthly_amount=Decimal(600)
    )

    # Jan=500, Feb=500, Mar=600, Apr=600
    result = compute_ytd_budget([b1, b2], 2026, 4)
    assert result == Decimal(2200)


def test_ytd_no_budget_returns_zero() -> None:
    result = compute_ytd_budget([], 2026, 6)
    assert result == Decimal(0)


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
    assert determine_health(Decimal(500), Decimal(500)) == "over_budget"


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
    budgets = [
        make_category_group_budget(
            group_id=food_gid,
            effective_from=date(2026, 1, 1),
            monthly_amount=Decimal(500),
        ),
    ]
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

    overview = compute_budget_overview(budgets, txs, lookup, groups, 2026, 1)

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
    budgets = [
        make_category_group_budget(
            group_id=food_gid,
            effective_from=date(2026, 1, 1),
            monthly_amount=Decimal(500),
        ),
    ]
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

    overview = compute_budget_overview(budgets, txs, lookup, groups, 2026, 1)

    assert overview.total_monthly_budget == Decimal(500)
    assert overview.total_monthly_spent == Decimal(200)


def test_overview_unbudgeted_groups_without_spending_excluded() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    auto_gid = UUID("aaaaaaaa-0000-0000-0000-000000000002")

    groups = [
        make_category_group(id=food_gid, name="Food & Dining"),
        make_category_group(id=auto_gid, name="Auto & Transport"),
    ]

    overview = compute_budget_overview([], [], {}, groups, 2026, 1)

    assert len(overview.group_statuses) == 0


def test_overview_empty() -> None:
    overview = compute_budget_overview([], [], {}, [], 2026, 1)

    assert overview.year == 2026
    assert overview.month == 1
    assert overview.group_statuses == []
    assert overview.total_monthly_budget == Decimal(0)
    assert overview.total_monthly_spent == Decimal(0)


def test_overview_ytd_computation() -> None:
    food_gid = UUID("aaaaaaaa-0000-0000-0000-000000000001")
    payer = UUID("bbbbbbbb-0000-0000-0000-000000000001")

    groups = [make_category_group(id=food_gid, name="Food & Dining")]
    budgets = [
        make_category_group_budget(
            group_id=food_gid,
            effective_from=date(2026, 1, 1),
            monthly_amount=Decimal(500),
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

    overview = compute_budget_overview(budgets, txs, lookup, groups, 2026, 3)

    status = overview.group_statuses[0]
    assert status.monthly_spent == Decimal(150)
    assert status.ytd_spent == Decimal(650)
    assert status.ytd_budget == Decimal(1500)
    assert status.monthly_health == "on_track"
    assert overview.total_ytd_budget == Decimal(1500)
    assert overview.total_ytd_spent == Decimal(650)
