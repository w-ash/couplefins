from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from src.application.use_cases.save_budget import SaveBudgetCommand, SaveBudgetUseCase
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import make_category_group, make_category_group_budget
from tests.fixtures.mocks import make_mock_uow


async def test_saves_budget_and_commits() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    uow.category_groups.get_by_id.return_value = group
    uow.category_group_budgets.save.return_value = make_category_group_budget(
        group_id=group.id
    )

    command = SaveBudgetCommand(
        group_id=group.id,
        monthly_amount=Decimal(500),
        effective_from=date(2026, 1, 1),
    )
    result = await SaveBudgetUseCase().execute(command, uow)

    uow.category_group_budgets.save.assert_called_once()
    saved = uow.category_group_budgets.save.call_args[0][0]
    assert saved.group_id == group.id
    assert saved.monthly_amount == Decimal(500)
    assert saved.effective_from == date(2026, 1, 1)
    uow.commit.assert_called_once()
    assert result.budget is not None


async def test_raises_not_found_for_missing_group() -> None:
    uow = make_mock_uow()
    uow.category_groups.get_by_id.return_value = None

    command = SaveBudgetCommand(
        group_id=UUID("00000000-0000-0000-0000-000000000001"),
        monthly_amount=Decimal(500),
        effective_from=date(2026, 1, 1),
    )

    with pytest.raises(NotFoundError):
        await SaveBudgetUseCase().execute(command, uow)


def test_rejects_zero_amount() -> None:
    with pytest.raises(ValueError, match="monthly_amount must be positive"):
        SaveBudgetCommand(
            group_id=UUID("00000000-0000-0000-0000-000000000001"),
            monthly_amount=Decimal(0),
            effective_from=date(2026, 1, 1),
        )


def test_rejects_negative_amount() -> None:
    with pytest.raises(ValueError, match="monthly_amount must be positive"):
        SaveBudgetCommand(
            group_id=UUID("00000000-0000-0000-0000-000000000001"),
            monthly_amount=Decimal(-100),
            effective_from=date(2026, 1, 1),
        )
