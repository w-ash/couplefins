from decimal import Decimal
from uuid import UUID

import pytest

from src.application.use_cases.save_budget import SaveBudgetCommand, SaveBudgetUseCase
from src.domain.exceptions import NotFoundError, PeriodFinalizedError
from tests.fixtures.factories import (
    make_category_group,
    make_category_group_budget,
    make_person,
    make_reconciliation_period,
)
from tests.fixtures.mocks import make_mock_uow


async def test_saves_budget_and_commits() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    uow.category_groups.get_by_id.return_value = group
    uow.category_group_budgets.get_by_month.return_value = []
    uow.category_group_budgets.save.return_value = make_category_group_budget(
        group_id=group.id
    )

    command = SaveBudgetCommand(
        group_id=group.id,
        monthly_amount=Decimal(500),
        year=2026,
        month=1,
    )
    result = await SaveBudgetUseCase().execute(command, uow)

    uow.category_group_budgets.save.assert_called_once()
    saved = uow.category_group_budgets.save.call_args[0][0]
    assert saved.group_id == group.id
    assert saved.monthly_amount == Decimal(500)
    assert saved.year == 2026
    assert saved.month == 1
    uow.commit.assert_called_once()
    assert result.budget is not None


async def test_upsert_reuses_existing_budget_id() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    existing = make_category_group_budget(group_id=group.id, year=2026, month=1)
    uow.category_groups.get_by_id.return_value = group
    uow.category_group_budgets.get_by_month.return_value = [existing]
    uow.category_group_budgets.save.return_value = make_category_group_budget(
        id=existing.id, group_id=group.id, monthly_amount=Decimal(700)
    )

    command = SaveBudgetCommand(
        group_id=group.id,
        monthly_amount=Decimal(700),
        year=2026,
        month=1,
    )
    await SaveBudgetUseCase().execute(command, uow)

    saved = uow.category_group_budgets.save.call_args[0][0]
    assert saved.id == existing.id
    assert saved.monthly_amount == Decimal(700)


async def test_raises_not_found_for_missing_group() -> None:
    uow = make_mock_uow()
    uow.category_groups.get_by_id.return_value = None

    command = SaveBudgetCommand(
        group_id=UUID("00000000-0000-0000-0000-000000000001"),
        monthly_amount=Decimal(500),
        year=2026,
        month=1,
    )

    with pytest.raises(NotFoundError):
        await SaveBudgetUseCase().execute(command, uow)


def test_rejects_zero_amount() -> None:
    with pytest.raises(ValueError, match="monthly_amount must be positive"):
        SaveBudgetCommand(
            group_id=UUID("00000000-0000-0000-0000-000000000001"),
            monthly_amount=Decimal(0),
            year=2026,
            month=1,
        )


def test_rejects_negative_amount() -> None:
    with pytest.raises(ValueError, match="monthly_amount must be positive"):
        SaveBudgetCommand(
            group_id=UUID("00000000-0000-0000-0000-000000000001"),
            monthly_amount=Decimal(-100),
            year=2026,
            month=1,
        )


async def test_saves_personal_budget_with_person_id() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    person = make_person(name="Alice")
    uow.category_groups.get_by_id.return_value = group
    uow.persons.get_by_id.return_value = person
    uow.category_group_budgets.get_by_month.return_value = []
    uow.category_group_budgets.save.return_value = make_category_group_budget(
        group_id=group.id, person_id=person.id
    )

    command = SaveBudgetCommand(
        group_id=group.id,
        monthly_amount=Decimal(300),
        year=2026,
        month=1,
        person_id=person.id,
    )
    result = await SaveBudgetUseCase().execute(command, uow)

    saved = uow.category_group_budgets.save.call_args[0][0]
    assert saved.person_id == person.id
    uow.persons.get_by_id.assert_called_once_with(person.id)
    assert result.budget.person_id == person.id


async def test_raises_not_found_for_missing_person() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    uow.category_groups.get_by_id.return_value = group
    uow.persons.get_by_id.return_value = None

    command = SaveBudgetCommand(
        group_id=group.id,
        monthly_amount=Decimal(300),
        year=2026,
        month=1,
        person_id=UUID("00000000-0000-0000-0000-000000000099"),
    )

    with pytest.raises(NotFoundError, match="Person"):
        await SaveBudgetUseCase().execute(command, uow)


async def test_finalized_period_raises() -> None:
    group = make_category_group()
    uow = make_mock_uow()
    uow.category_groups.get_by_id.return_value = group
    uow.reconciliation_periods.get_by_period.return_value = make_reconciliation_period(
        year=2026, month=1, is_finalized=True
    )

    command = SaveBudgetCommand(
        group_id=group.id,
        monthly_amount=Decimal("500.00"),
        year=2026,
        month=1,
    )
    with pytest.raises(PeriodFinalizedError):
        await SaveBudgetUseCase().execute(command, uow)
    uow.category_group_budgets.save.assert_not_called()
