from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest

from src.application.chat.pending_actions import PendingAction
from src.application.chat.registry import execute_confirmed_action
from src.domain.exceptions import PeriodFinalizedError, ValidationError
from tests.fixtures.factories import (
    make_category_group,
    make_person,
    make_reconciliation_period,
    make_transaction,
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


async def test_exec_bulk_runs_tags_and_fields_in_one_uow() -> None:
    """Both mutations share a single UoW and a single commit."""
    user = make_person(name="Alice")
    tx = make_transaction(tags=("shared",), category="Dining Out")

    uow = make_mock_uow()
    uow.transactions.get_by_ids.return_value = [tx]

    action = PendingAction(
        action_id=uuid4(),
        person_id=user.id,
        tool_name="bulk_update_transactions",
        tool_input={},
        description="Update 1 transaction: add tags: discuss, exclude",
        details={
            "transaction_ids": [str(tx.id)],
            "count": 1,
            "changes": {
                "tags": {"action": "add", "values": ["discuss"]},
                "is_excluded": True,
            },
        },
        created_at=datetime.now(UTC),
    )

    async def run_with_mock_uow(factory):
        return await factory(uow)

    with patch(
        "src.application.chat.confirmed_actions.execute_use_case",
        run_with_mock_uow,
    ):
        result = await execute_confirmed_action(action, user)

    assert result[0]["updated_count"] == 2
    uow.commit.assert_called_once()


async def test_exec_bulk_atomic_rollback_on_field_failure() -> None:
    """A failing field update (unknown category) must not leave the tag
    change durably committed — the two mutations run as one atomic
    operation with a single commit at the very end."""
    user = make_person(name="Alice")
    tx = make_transaction(tags=("shared",), category="Dining Out")

    uow = make_mock_uow()
    uow.transactions.get_by_ids.return_value = [tx]
    uow.categories.get_by_name.return_value = None  # unknown category

    action = PendingAction(
        action_id=uuid4(),
        person_id=user.id,
        tool_name="bulk_update_transactions",
        tool_input={},
        description="Update 1 transaction: add tags: discuss, category to Bogus",
        details={
            "transaction_ids": [str(tx.id)],
            "count": 1,
            "changes": {
                "tags": {"action": "add", "values": ["discuss"]},
                "category": "Bogus",
            },
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
        pytest.raises(ValidationError, match="Unknown category"),
    ):
        await execute_confirmed_action(action, user)

    # The tag mutation staged its edit, but since the field mutation failed
    # before the single shared commit, nothing was ever durably persisted.
    uow.transaction_edits.save_batch.assert_called_once()
    uow.commit.assert_not_called()


# --- v1.8.2 executors ---


def _action(tool_name: str, details: dict[str, object]) -> PendingAction:
    return PendingAction(
        action_id=uuid4(),
        person_id=make_person(name="Alice").id,
        tool_name=tool_name,
        tool_input={},
        description=f"{tool_name} proposal",
        details=details,
        created_at=datetime.now(UTC),
    )


async def test_exec_finalize_locks_open_period() -> None:
    user = make_person(name="Alice")
    uow = make_mock_uow()
    uow.reconciliation_periods.get_by_period.return_value = None
    saved = make_reconciliation_period(year=2026, month=3, is_finalized=True)
    uow.reconciliation_periods.save.return_value = saved

    async def run_with_mock_uow(factory):
        return await factory(uow)

    action = _action(
        "finalize_period", {"year": 2026, "month": 3, "notes": "", "warnings": []}
    )
    with patch(
        "src.application.chat.confirmed_actions.execute_use_case",
        run_with_mock_uow,
    ):
        result, entity = await execute_confirmed_action(action, user)

    assert result["status"] == "confirmed"
    assert entity == "reconciliation"
    uow.reconciliation_periods.save.assert_called_once()
    uow.commit.assert_called_once()


async def test_exec_finalize_toctou_already_finalized() -> None:
    """The partner finalized between propose and confirm — reject."""
    user = make_person(name="Alice")
    uow = make_mock_uow()
    uow.reconciliation_periods.get_by_period.return_value = make_reconciliation_period(
        year=2026, month=3, is_finalized=True
    )

    async def run_with_mock_uow(factory):
        return await factory(uow)

    action = _action("finalize_period", {"year": 2026, "month": 3})
    with (
        patch(
            "src.application.chat.confirmed_actions.execute_use_case",
            run_with_mock_uow,
        ),
        pytest.raises(ValidationError, match="already finalized"),
    ):
        await execute_confirmed_action(action, user)

    uow.reconciliation_periods.save.assert_not_called()


async def test_exec_delete_settlement_toctou_gone() -> None:
    """The settlement was deleted between propose and confirm — reject."""
    from src.domain.exceptions import NotFoundError

    user = make_person(name="Alice")
    uow = make_mock_uow()
    uow.settlements.get_by_id.return_value = None

    async def run_with_mock_uow(factory):
        return await factory(uow)

    action = _action("delete_settlement", {"settlement_id": str(uuid4())})
    with (
        patch(
            "src.application.chat.confirmed_actions.execute_use_case",
            run_with_mock_uow,
        ),
        pytest.raises(NotFoundError),
    ):
        await execute_confirmed_action(action, user)

    uow.settlements.delete.assert_not_called()


async def test_exec_unlink_toctou_link_gone() -> None:
    """The link disappeared between propose and confirm — report, don't
    pretend the confirmation changed anything."""
    from tests.fixtures.factories import make_settlement

    user = make_person(name="Alice")
    tx = make_transaction()
    settlement = make_settlement()
    uow = make_mock_uow()
    uow.settlements.get_by_id.return_value = settlement
    uow.transactions.get_by_id.return_value = tx
    uow.reconciliation_periods.get_by_period.return_value = None
    uow.settlement_transaction_links.delete_by_settlement_and_transaction.return_value = 0

    async def run_with_mock_uow(factory):
        return await factory(uow)

    action = _action(
        "unlink_settlement_transaction",
        {"settlement_id": str(settlement.id), "transaction_id": str(tx.id)},
    )
    with (
        patch(
            "src.application.chat.confirmed_actions.execute_use_case",
            run_with_mock_uow,
        ),
        pytest.raises(ValidationError, match="no longer linked"),
    ):
        await execute_confirmed_action(action, user)


async def test_exec_map_categories_uses_raw_details_values() -> None:
    """Details carry RAW category names (UserData marker, no tags) — the
    executor passes them through to the use case unchanged."""
    user = make_person(name="Alice")
    group = make_category_group()
    uow = make_mock_uow()
    uow.category_groups.get_by_ids.return_value = [group]
    uow.categories.get_all.return_value = []

    async def run_with_mock_uow(factory):
        return await factory(uow)

    action = _action(
        "map_categories",
        {
            "mappings": [
                {
                    "category": "Pets",
                    "group_name": group.name,
                    "group_id": str(group.id),
                }
            ],
            "count": 1,
        },
    )
    with patch(
        "src.application.chat.confirmed_actions.execute_use_case",
        run_with_mock_uow,
    ):
        result, entity = await execute_confirmed_action(action, user)

    assert result["updated_count"] == 1
    assert entity == "reconciliation"
    saved = uow.categories.save_batch.call_args.args[0]
    assert saved[0].name == "Pets"


async def test_exec_split_batch_updates_every_entry() -> None:
    """The executor reads the splits list, not the flat single-entry keys."""
    user = make_person(name="Alice")
    tx_a = make_transaction(payer_percentage=50)
    tx_b = make_transaction(payer_percentage=50)
    uow = make_mock_uow()
    uow.transactions.get_by_ids.return_value = [tx_a, tx_b]
    uow.reconciliation_periods.get_by_period.return_value = None

    async def run_with_mock_uow(factory):
        return await factory(uow)

    action = _action(
        "update_transaction_split",
        {
            "splits": [
                {"transaction_id": str(tx_a.id), "payer_percentage": 60},
                {"transaction_id": str(tx_b.id), "payer_percentage": 60},
            ],
            "count": 2,
        },
    )
    with patch(
        "src.application.chat.confirmed_actions.execute_use_case",
        run_with_mock_uow,
    ):
        result, _entity = await execute_confirmed_action(action, user)

    assert result["updated_count"] == 2
