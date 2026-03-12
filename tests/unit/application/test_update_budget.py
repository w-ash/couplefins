from decimal import Decimal
from uuid import UUID

import pytest

from src.application.use_cases.update_budget import (
    UpdateBudgetCommand,
    UpdateBudgetUseCase,
)
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import make_category_group_budget
from tests.fixtures.mocks import make_mock_uow


async def test_updates_amount_and_commits() -> None:
    uow = make_mock_uow()
    existing = make_category_group_budget(monthly_amount=Decimal(500))
    uow.category_group_budgets.get_by_id.return_value = existing
    uow.category_group_budgets.save.return_value = make_category_group_budget(
        id=existing.id,
        group_id=existing.group_id,
        monthly_amount=Decimal(600),
        effective_from=existing.effective_from,
    )

    command = UpdateBudgetCommand(budget_id=existing.id, monthly_amount=Decimal(600))
    result = await UpdateBudgetUseCase().execute(command, uow)

    uow.category_group_budgets.save.assert_called_once()
    saved = uow.category_group_budgets.save.call_args[0][0]
    assert saved.monthly_amount == Decimal(600)
    assert saved.group_id == existing.group_id
    assert saved.effective_from == existing.effective_from
    uow.commit.assert_called_once()
    assert result.budget is not None


async def test_raises_not_found_for_missing_budget() -> None:
    uow = make_mock_uow()
    uow.category_group_budgets.get_by_id.return_value = None

    command = UpdateBudgetCommand(
        budget_id=UUID("00000000-0000-0000-0000-000000000001"),
        monthly_amount=Decimal(600),
    )

    with pytest.raises(NotFoundError):
        await UpdateBudgetUseCase().execute(command, uow)


def test_rejects_zero_amount() -> None:
    with pytest.raises(ValueError, match="monthly_amount must be positive"):
        UpdateBudgetCommand(
            budget_id=UUID("00000000-0000-0000-0000-000000000001"),
            monthly_amount=Decimal(0),
        )
