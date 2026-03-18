from datetime import date
from decimal import Decimal

import pytest

from src.application.use_cases.get_spending_trends import (
    GetSpendingTrendsCommand,
    GetSpendingTrendsUseCase,
)
from tests.fixtures.factories import (
    make_category_group,
    make_category_group_budget,
    make_category_mapping,
    make_person,
    make_settlement,
    make_transaction,
)
from tests.fixtures.mocks import make_mock_uow


def _setup_uow():
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    uow.persons.get_all.return_value = [alice, bob]

    food_group = make_category_group(name="Food & Dining")
    uow.category_groups.get_all.return_value = [food_group]

    mapping = make_category_mapping(category="Dining Out", group_id=food_group.id)
    uow.category_mappings.get_all.return_value = [mapping]

    uow.category_group_budgets.get_all.return_value = []

    return uow, alice, bob, food_group


async def test_happy_path() -> None:
    uow, alice, _, food_group = _setup_uow()
    uow.transactions.get_shared_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-80.00"),
            payer_person_id=alice.id,
        ),
        make_transaction(
            date=date(2026, 2, 5),
            category="Dining Out",
            amount=Decimal("-60.00"),
            payer_person_id=alice.id,
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.year == 2026
    assert len(result.trends.monthly_group_spending) == 2
    assert len(result.trends.monthly_totals) == 2
    assert len(result.trends.group_summaries) == 1
    assert result.trends.group_summaries[0].group_id == food_group.id
    assert result.trends.group_summaries[0].ytd_total == Decimal("140.00")


async def test_no_data() -> None:
    uow, _, _, _ = _setup_uow()
    uow.transactions.get_shared_by_year.return_value = []

    command = GetSpendingTrendsCommand(year=2026)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.year == 2026
    assert result.trends.monthly_group_spending == []
    assert result.trends.monthly_totals == []
    assert result.trends.group_summaries == []
    assert result.comparison_cards == []
    assert result.budget_lines == {}
    assert result.settlement_trend == []


def test_invalid_year() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        GetSpendingTrendsCommand(year=0)


def test_invalid_month() -> None:
    with pytest.raises(ValueError, match="must be 1-12"):
        GetSpendingTrendsCommand(year=2026, month=13)


async def test_comparison_cards_computed() -> None:
    uow, alice, _, food_group = _setup_uow()
    uow.transactions.get_shared_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
        ),
        make_transaction(
            date=date(2026, 2, 10),
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
        ),
        make_transaction(
            date=date(2026, 3, 10),
            category="Dining Out",
            amount=Decimal("-200.00"),
            payer_person_id=alice.id,
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026, month=3)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.month == 3
    assert len(result.comparison_cards) == 1
    card = result.comparison_cards[0]
    assert card.group_id == food_group.id
    assert card.current_month_amount == Decimal("200.00")
    assert card.trailing_average == Decimal("100.00")


async def test_budget_lines_populated() -> None:
    uow, alice, _, food_group = _setup_uow()
    uow.transactions.get_shared_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
        ),
    ]
    uow.category_group_budgets.get_all.return_value = [
        make_category_group_budget(
            group_id=food_group.id,
            monthly_amount=Decimal("500.00"),
            effective_from=date(2026, 1, 1),
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026, month=1)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert food_group.id in result.budget_lines
    assert result.budget_lines[food_group.id] == Decimal("500.00")


async def test_budget_lines_empty_when_no_budgets() -> None:
    uow, _, _, _ = _setup_uow()
    uow.transactions.get_shared_by_year.return_value = []

    command = GetSpendingTrendsCommand(year=2026, month=1)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.budget_lines == {}


async def test_settlement_trend_populated() -> None:
    uow, alice, _bob, _food_group = _setup_uow()
    uow.transactions.get_shared_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
        ),
        make_transaction(
            date=date(2026, 2, 10),
            category="Dining Out",
            amount=Decimal("-80.00"),
            payer_person_id=alice.id,
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026, month=2)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert len(result.settlement_trend) == 2
    jan = result.settlement_trend[0]
    assert jan.month == 1
    assert jan.amount > 0
    assert jan.is_settled is False


async def test_settlement_trend_marks_settled() -> None:
    uow, alice, bob, _food_group = _setup_uow()
    uow.transactions.get_shared_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
        ),
    ]
    # Settlement that covers the owed amount
    uow.settlements.get_by_year.return_value = [
        make_settlement(
            year=2026,
            month=1,
            amount=Decimal("50.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026, month=1)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert len(result.settlement_trend) == 1
    assert result.settlement_trend[0].is_settled is True


async def test_persons_included() -> None:
    uow, _alice, _bob, _ = _setup_uow()
    uow.transactions.get_shared_by_year.return_value = []

    command = GetSpendingTrendsCommand(year=2026)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert len(result.persons) == 2
    names = {p.name for p in result.persons}
    assert names == {"Alice", "Bob"}


async def test_comparison_year_returns_both_years() -> None:
    uow, alice, _, _food_group = _setup_uow()

    current_txs = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-80.00"),
            payer_person_id=alice.id,
        ),
    ]
    comparison_txs = [
        make_transaction(
            date=date(2025, 1, 10),
            category="Dining Out",
            amount=Decimal("-60.00"),
            payer_person_id=alice.id,
        ),
    ]

    uow.transactions.get_shared_by_year.side_effect = lambda year: (
        current_txs if year == 2026 else comparison_txs
    )

    command = GetSpendingTrendsCommand(year=2026, comparison_year=2025)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert len(result.trends.monthly_group_spending) == 1
    assert result.trends.monthly_group_spending[0].amount == Decimal("80.00")

    assert len(result.comparison_monthly_group_spending) == 1
    assert result.comparison_monthly_group_spending[0].year == 2025
    assert result.comparison_monthly_group_spending[0].amount == Decimal("60.00")


async def test_comparison_year_none_returns_empty() -> None:
    uow, alice, _, _ = _setup_uow()
    uow.transactions.get_shared_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.comparison_monthly_group_spending == []


async def test_comparison_year_no_data() -> None:
    uow, alice, _, _ = _setup_uow()
    uow.transactions.get_shared_by_year.side_effect = lambda year: (
        [
            make_transaction(
                date=date(2026, 1, 10),
                category="Dining Out",
                amount=Decimal("-50.00"),
                payer_person_id=alice.id,
            ),
        ]
        if year == 2026
        else []
    )

    command = GetSpendingTrendsCommand(year=2026, comparison_year=2025)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.comparison_monthly_group_spending == []


def test_invalid_comparison_year() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        GetSpendingTrendsCommand(year=2026, comparison_year=0)
