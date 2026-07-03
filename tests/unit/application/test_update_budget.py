from decimal import Decimal
from uuid import UUID

import pytest

from src.application.use_cases.update_budget import (
    UpdateBudgetCommand,
    UpdateBudgetUseCase,
)
from src.domain.exceptions import (
    ForbiddenError,
    NotFoundError,
    PeriodFinalizedError,
)
from tests.fixtures.factories import (
    make_category_group_budget,
    make_reconciliation_period,
)
from tests.fixtures.mocks import make_mock_uow

ALICE = UUID("bbbbbbbb-0000-0000-0000-000000000001")
BOB = UUID("bbbbbbbb-0000-0000-0000-000000000002")


async def test_updates_amount_and_commits() -> None:
    uow = make_mock_uow()
    existing = make_category_group_budget(monthly_amount=Decimal(500))
    uow.category_group_budgets.get_by_id.return_value = existing
    uow.category_group_budgets.save.return_value = make_category_group_budget(
        id=existing.id,
        group_id=existing.group_id,
        monthly_amount=Decimal(600),
    )

    command = UpdateBudgetCommand(
        budget_id=existing.id, monthly_amount=Decimal(600), person_id=ALICE
    )
    result = await UpdateBudgetUseCase().execute(command, uow)

    uow.category_group_budgets.save.assert_called_once()
    saved = uow.category_group_budgets.save.call_args[0][0]
    assert saved.monthly_amount == Decimal(600)
    assert saved.group_id == existing.group_id
    assert saved.year == existing.year
    assert saved.month == existing.month
    uow.commit.assert_called_once()
    assert result.budget is not None


async def test_raises_not_found_for_missing_budget() -> None:
    uow = make_mock_uow()
    uow.category_group_budgets.get_by_id.return_value = None

    command = UpdateBudgetCommand(
        budget_id=UUID("00000000-0000-0000-0000-000000000001"),
        monthly_amount=Decimal(600),
        person_id=ALICE,
    )

    with pytest.raises(NotFoundError):
        await UpdateBudgetUseCase().execute(command, uow)


def test_rejects_zero_amount() -> None:
    with pytest.raises(ValueError, match="monthly_amount must be positive"):
        UpdateBudgetCommand(
            budget_id=UUID("00000000-0000-0000-0000-000000000001"),
            monthly_amount=Decimal(0),
            person_id=ALICE,
        )


async def test_rejects_other_persons_personal_budget() -> None:
    uow = make_mock_uow()
    existing = make_category_group_budget(monthly_amount=Decimal(500), person_id=ALICE)
    uow.category_group_budgets.get_by_id.return_value = existing

    command = UpdateBudgetCommand(
        budget_id=existing.id, monthly_amount=Decimal(600), person_id=BOB
    )

    with pytest.raises(ForbiddenError):
        await UpdateBudgetUseCase().execute(command, uow)


async def test_allows_editing_household_budget() -> None:
    """Household budgets (person_id=None) are editable by anyone."""
    uow = make_mock_uow()
    existing = make_category_group_budget(monthly_amount=Decimal(500), person_id=None)
    uow.category_group_budgets.get_by_id.return_value = existing
    uow.category_group_budgets.save.return_value = make_category_group_budget(
        id=existing.id, monthly_amount=Decimal(600)
    )

    command = UpdateBudgetCommand(
        budget_id=existing.id, monthly_amount=Decimal(600), person_id=ALICE
    )
    result = await UpdateBudgetUseCase().execute(command, uow)
    assert result.budget is not None


async def test_finalized_period_raises() -> None:
    existing = make_category_group_budget(year=2026, month=1)
    uow = make_mock_uow()
    uow.category_group_budgets.get_by_id.return_value = existing
    uow.reconciliation_periods.get_by_period.return_value = make_reconciliation_period(
        year=2026, month=1, is_finalized=True
    )

    command = UpdateBudgetCommand(
        budget_id=existing.id,
        monthly_amount=Decimal("600.00"),
        person_id=UUID(int=1),
    )
    with pytest.raises(PeriodFinalizedError):
        await UpdateBudgetUseCase().execute(command, uow)
    uow.category_group_budgets.save.assert_not_called()
