from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest

from src.application.chat.confirmed_actions import execute_confirmed_action
from src.application.chat.pending_actions import PendingAction
from src.domain.exceptions import PeriodFinalizedError
from tests.fixtures.factories import (
    make_category_group,
    make_person,
    make_reconciliation_period,
)
from tests.fixtures.mocks import make_mock_uow


async def test_confirmed_budget_update_rejected_when_month_finalized() -> None:
    """TOCTOU guard: the action was proposed while the month was open, the
    partner finalized it, then the user clicked Confirm — the use-case-level
    finalization guard must reject at execute time."""
    group = make_category_group()
    user = make_person(name="Alice")

    uow = make_mock_uow()
    uow.category_groups.get_by_id.return_value = group
    uow.reconciliation_periods.get_by_period.return_value = make_reconciliation_period(
        year=2026, month=4, is_finalized=True
    )

    action = PendingAction(
        action_id=uuid4(),
        person_id=user.id,
        tool_name="update_budget",
        tool_input={},
        description="Set Food & Dining to $700.00 for April 2026",
        details={
            "group_id": str(group.id),
            "amount": "700.00",
            "year": 2026,
            "month": 4,
        },
        created_at=datetime.now(UTC),
    )

    async def run_with_mock_uow(factory):
        return await factory(uow)

    with (
        patch(
            "src.application.chat.confirmed_actions.execute_use_case",
            run_with_mock_uow,
        ),
        pytest.raises(PeriodFinalizedError),
    ):
        await execute_confirmed_action(action, user)

    uow.category_group_budgets.save.assert_not_called()
