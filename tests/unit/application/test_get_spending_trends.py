from datetime import date
from decimal import Decimal

import pytest

from src.application.use_cases.get_spending_trends import (
    GetSpendingTrendsCommand,
    GetSpendingTrendsUseCase,
)
from tests.fixtures.factories import (
    make_category_group,
    make_category_mapping,
    make_person,
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

    return uow, alice, food_group


async def test_happy_path() -> None:
    uow, alice, food_group = _setup_uow()
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
    uow, _, _ = _setup_uow()
    uow.transactions.get_shared_by_year.return_value = []

    command = GetSpendingTrendsCommand(year=2026)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.year == 2026
    assert result.trends.monthly_group_spending == []
    assert result.trends.monthly_totals == []
    assert result.trends.group_summaries == []


def test_invalid_year() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        GetSpendingTrendsCommand(year=0)
