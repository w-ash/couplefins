"""Tests for mutation tool handlers in the chat tool executor.

Each mutation handler stores a pending action and returns a
pending_confirmation response — it never executes the mutation directly.
"""

from unittest.mock import AsyncMock, patch
import uuid

import pytest

from src.application.chat.pending_actions import pending_action_store
from src.application.chat.tool_executor import execute_tool
from src.application.use_cases.list_category_groups import (
    CategoryGroupWithCategories,
    ListCategoryGroupsResult,
)
from src.domain.entities.category_group import CategoryGroup
from src.domain.exceptions import ToolExecutionError
from tests.fixtures.factories import make_person, make_transaction

ALICE = make_person(name="Alice", id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
BOB = make_person(name="Bob", id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
PERSONS = [ALICE, BOB]

FOOD_GROUP_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _group_list_result() -> ListCategoryGroupsResult:
    group = CategoryGroup(id=FOOD_GROUP_ID, name="Food & Dining")
    return ListCategoryGroupsResult(
        items=[CategoryGroupWithCategories(group=group, categories=[])]
    )


@pytest.fixture(autouse=True)
def _clear_pending_actions() -> None:
    """Clear pending actions between tests."""
    pending_action_store._actions.clear()


# --- update_budget ---


@pytest.mark.anyio
async def test_update_budget_returns_pending_confirmation() -> None:
    """update_budget stores a pending action and returns confirmation."""
    mock_results = [
        (False, None),  # _check_finalization
        _group_list_result(),  # _resolve_category_group_id
    ]

    def side_effect(fn: object) -> object:
        return mock_results.pop(0)

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        side_effect=side_effect,
    ):
        result = await execute_tool(
            "update_budget",
            {"group_name": "Food & Dining", "amount": 700, "year": 2026, "month": 4},
            ALICE,
            PERSONS,
        )

    assert result["status"] == "pending_confirmation"
    assert "action_id" in result
    assert "Food & Dining" in str(result["description"])
    assert "$700.00" in str(result["description"])
    assert result["details"]["group_id"] == str(FOOD_GROUP_ID)
    assert result["details"]["scope"] == "household"


@pytest.mark.anyio
async def test_update_budget_unknown_group_raises() -> None:
    """update_budget raises ToolExecutionError for unknown group."""
    mock_results = [
        (False, None),  # _check_finalization
        ListCategoryGroupsResult(items=[]),  # empty groups
    ]

    def side_effect(fn: object) -> object:
        return mock_results.pop(0)

    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            new_callable=AsyncMock,
            side_effect=side_effect,
        ),
        pytest.raises(ToolExecutionError, match="Unknown category group"),
    ):
        await execute_tool(
            "update_budget",
            {"group_name": "Nonexistent", "amount": 100, "year": 2026, "month": 4},
            ALICE,
            PERSONS,
        )


# --- update_transaction_split ---


@pytest.mark.anyio
async def test_update_transaction_split_returns_pending() -> None:
    """update_transaction_split stores pending action with tx details."""
    tx = make_transaction(
        merchant="Whole Foods",
        payer_percentage=50,
        payer_person_id=ALICE.id,
    )
    tx_info = {
        "merchant": tx.merchant,
        "date": tx.date.isoformat(),
        "amount": float(round(tx.amount, 2)),
        "current_split": f"{tx.payer_percentage}/{100 - tx.payer_percentage}",
        "payer": "Alice",
        "year": tx.date.year,
        "month": tx.date.month,
    }
    mock_results = [
        tx_info,  # _fetch in handler
        (False, None),  # _check_finalization
    ]

    def side_effect(fn: object) -> object:
        return mock_results.pop(0)

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        side_effect=side_effect,
    ):
        result = await execute_tool(
            "update_transaction_split",
            {"transaction_id": str(tx.id), "payer_percentage": 70},
            ALICE,
            PERSONS,
        )

    assert result["status"] == "pending_confirmation"
    assert result["details"]["new_split"] == "70/30"
    assert result["details"]["transaction_id"] == str(tx.id)


@pytest.mark.anyio
async def test_update_transaction_split_invalid_uuid_raises() -> None:
    with pytest.raises(ToolExecutionError, match="Invalid transaction ID"):
        await execute_tool(
            "update_transaction_split",
            {"transaction_id": "not-a-uuid", "payer_percentage": 50},
            ALICE,
            PERSONS,
        )


# --- bulk_update_transactions ---


@pytest.mark.anyio
async def test_bulk_update_exceeds_limit_raises() -> None:
    """bulk_update_transactions rejects >100 IDs."""
    ids = [str(uuid.uuid4()) for _ in range(101)]
    with pytest.raises(ToolExecutionError, match="Maximum 100"):
        await execute_tool(
            "bulk_update_transactions",
            {"transaction_ids": ids, "changes": {"household": True}},
            ALICE,
            PERSONS,
        )


@pytest.mark.anyio
async def test_bulk_update_returns_pending() -> None:
    """bulk_update_transactions stores pending action for valid input."""
    tx = make_transaction(payer_person_id=ALICE.id)

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=None,  # _validate passes
    ):
        result = await execute_tool(
            "bulk_update_transactions",
            {
                "transaction_ids": [str(tx.id)],
                "changes": {
                    "household": True,
                    "tags": {"action": "add", "values": ["discuss"]},
                },
            },
            ALICE,
            PERSONS,
        )

    assert result["status"] == "pending_confirmation"
    assert result["details"]["count"] == 1
    assert "household=true" in str(result["description"])
    assert "add tags: discuss" in str(result["description"])


# --- search_transactions includes id ---


@pytest.mark.anyio
async def test_search_transactions_includes_id() -> None:
    """Regression: search_transactions must return transaction IDs."""
    from src.application.use_cases.search_transactions import SearchTransactionsResult

    tx = make_transaction(merchant="Test Store", payer_person_id=ALICE.id)
    search_result = SearchTransactionsResult(transactions=[tx], total_count=1)

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=search_result,
    ):
        result = await execute_tool(
            "search_transactions",
            {"year": 2026, "month": 3},
            ALICE,
            PERSONS,
        )

    assert "id" in result["transactions"][0]
    assert result["transactions"][0]["id"] == str(tx.id)
