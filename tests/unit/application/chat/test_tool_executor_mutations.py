"""Tests for mutation tool handlers in the chat tool executor.

Each mutation handler stores a pending action and returns a
pending_confirmation response — it never executes the mutation directly.
"""

from unittest.mock import AsyncMock, patch
import uuid

import pytest

from src.application.chat.pending_actions import pending_action_store
from src.application.chat.registry import execute_tool
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


def _split_row(tx: object, payer_percentage: int) -> dict[str, object]:
    """Mirror the row shape the handler's single-UoW _fetch builds."""
    return {
        "transaction_id": str(tx.id),  # type: ignore[attr-defined]
        "merchant": f"<user_data>{tx.merchant}</user_data>",  # type: ignore[attr-defined]
        "date": tx.date.isoformat(),  # type: ignore[attr-defined]
        "amount": float(round(tx.amount, 2)),  # type: ignore[attr-defined]
        "payer": "Alice",
        "current_split": "50/50",
        "new_split": f"{payer_percentage}/{100 - payer_percentage}",
        "payer_percentage": payer_percentage,
    }


@pytest.mark.anyio
async def test_update_transaction_split_returns_pending() -> None:
    """update_transaction_split stores pending action with tx details."""
    tx = make_transaction(
        merchant="Whole Foods",
        payer_percentage=50,
        payer_person_id=ALICE.id,
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=[_split_row(tx, 70)],  # single-UoW _fetch result
    ):
        result = await execute_tool(
            "update_transaction_split",
            {"transaction_id": str(tx.id), "payer_percentage": 70},
            ALICE,
            PERSONS,
        )

    assert result["status"] == "pending_confirmation"
    # Single-entry proposals keep the flat keys the SplitDetails card reads.
    assert result["details"]["new_split"] == "70/30"
    assert result["details"]["transaction_id"] == str(tx.id)
    # The executor always reads the splits list.
    assert result["details"]["count"] == 1
    assert result["details"]["splits"][0]["payer_percentage"] == 70


@pytest.mark.anyio
async def test_update_transaction_split_batch_returns_pending() -> None:
    """The batch splits form proposes one action covering every entry."""
    tx_a = make_transaction(merchant="Rent Co", payer_person_id=ALICE.id)
    tx_b = make_transaction(merchant="Rent Co", payer_person_id=ALICE.id)
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=[_split_row(tx_a, 60), _split_row(tx_b, 60)],
    ):
        result = await execute_tool(
            "update_transaction_split",
            {
                "splits": [
                    {"transaction_id": str(tx_a.id), "payer_percentage": 60},
                    {"transaction_id": str(tx_b.id), "payer_percentage": 60},
                ]
            },
            ALICE,
            PERSONS,
        )

    assert result["status"] == "pending_confirmation"
    assert result["details"]["count"] == 2
    assert "2 transactions to 60/40" in str(result["description"])
    # No flat single-entry keys on batch proposals.
    assert "transaction_id" not in result["details"]


@pytest.mark.anyio
async def test_update_transaction_split_requires_some_form() -> None:
    with pytest.raises(ToolExecutionError, match="transaction_id"):
        await execute_tool("update_transaction_split", {}, ALICE, PERSONS)


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


# --- v1.8.2 write tools (propose handlers) ---


def _settle_data(
    *, is_finalized: bool = False, warnings: list[str] | None = None
) -> object:
    from decimal import Decimal

    from src.application.use_cases.get_settle_up_data import GetSettleUpDataResult

    return GetSettleUpDataResult(
        year=2026,
        month=3,
        owed=None,
        net_position=None,
        recorded_settlements=[],
        remaining_balance=Decimal(0),
        outstanding=None,
        outstanding_span=None,
        ledger_months=[],
        all_settlements=[],
        upload_statuses=[],
        persons=PERSONS,
        is_finalized=is_finalized,
        finalized_at=None,
        transaction_count=82,
        latest_transaction_month=(2026, 3),
        finalization_warnings=warnings or [],
        payer_splits=[],
        payer_group_splits=[],
    )


@pytest.mark.anyio
async def test_delete_budget_returns_pending_with_current_amount() -> None:
    from decimal import Decimal

    from src.application.use_cases.list_budgets import ListBudgetsResult
    from tests.fixtures.factories import make_category_group_budget

    budget = make_category_group_budget(
        group_id=FOOD_GROUP_ID, monthly_amount=Decimal("700.00"), year=2026, month=3
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        side_effect=[
            (False, None),  # _check_finalization
            _group_list_result(),  # _require_group
            ListBudgetsResult(budgets=[budget]),
        ],
    ):
        result = await execute_tool(
            "delete_budget",
            {"group_name": "Food & Dining", "year": 2026, "month": 3},
            ALICE,
            PERSONS,
        )

    assert result["status"] == "pending_confirmation"
    assert result["details"]["budget_id"] == str(budget.id)
    assert result["details"]["current_amount"] == pytest.approx(700.0)
    assert "$700.00" in str(result["description"])


@pytest.mark.anyio
async def test_delete_budget_missing_budget_raises() -> None:
    from src.application.use_cases.list_budgets import ListBudgetsResult

    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            new_callable=AsyncMock,
            side_effect=[
                (False, None),
                _group_list_result(),
                ListBudgetsResult(budgets=[]),
            ],
        ),
        pytest.raises(ToolExecutionError, match="No household budget"),
    ):
        await execute_tool(
            "delete_budget",
            {"group_name": "Food & Dining", "year": 2026, "month": 3},
            ALICE,
            PERSONS,
        )


@pytest.mark.anyio
async def test_copy_budgets_counts_skips() -> None:
    from src.application.use_cases.list_budgets import ListBudgetsResult
    from tests.fixtures.factories import make_category_group_budget

    other_group = uuid.uuid4()
    budgets = ListBudgetsResult(
        budgets=[
            make_category_group_budget(group_id=FOOD_GROUP_ID, year=2026, month=3),
            make_category_group_budget(group_id=other_group, year=2026, month=3),
            # Target already has the Food & Dining budget → skipped.
            make_category_group_budget(group_id=FOOD_GROUP_ID, year=2026, month=4),
        ]
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        side_effect=[(False, None), budgets],
    ):
        result = await execute_tool(
            "copy_budgets",
            {"from_year": 2026, "from_month": 3, "to_year": 2026, "to_month": 4},
            ALICE,
            PERSONS,
        )

    assert result["details"]["copy_count"] == 1
    assert result["details"]["skipped_count"] == 1


@pytest.mark.anyio
async def test_manage_category_group_rename_unknown_lists_valid_names() -> None:
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            new_callable=AsyncMock,
            return_value=_group_list_result(),
        ),
        pytest.raises(ToolExecutionError, match="Valid groups: Food & Dining"),
    ):
        await execute_tool(
            "manage_category_group",
            {"action": "rename", "name": "Bogus", "new_name": "Better"},
            ALICE,
            PERSONS,
        )


@pytest.mark.anyio
async def test_manage_category_group_delete_surfaces_category_fate() -> None:
    from src.domain.entities.category_group import CategoryGroup
    from tests.fixtures.factories import make_category

    lifestyle_id = uuid.uuid4()
    groups = ListCategoryGroupsResult(
        items=[
            CategoryGroupWithCategories(
                group=CategoryGroup(id=FOOD_GROUP_ID, name="Food & Dining"),
                categories=[
                    make_category(name="Groceries", group_id=FOOD_GROUP_ID),
                    make_category(name="Dining Out", group_id=FOOD_GROUP_ID),
                ],
            ),
            CategoryGroupWithCategories(
                group=CategoryGroup(id=lifestyle_id, name="Lifestyle"),
                categories=[],
            ),
        ]
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=groups,
    ):
        result = await execute_tool(
            "manage_category_group",
            {
                "action": "delete",
                "name": "Food & Dining",
                "move_categories_to": "Lifestyle",
            },
            ALICE,
            PERSONS,
        )

    assert result["details"]["category_count"] == 2
    assert result["details"]["move_to_group_id"] == str(lifestyle_id)
    assert "move to Lifestyle" in str(result["description"])


@pytest.mark.anyio
async def test_map_categories_unknown_group_lists_valid_names() -> None:
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            new_callable=AsyncMock,
            return_value=_group_list_result(),
        ),
        pytest.raises(ToolExecutionError, match="Valid groups: Food & Dining"),
    ):
        await execute_tool(
            "map_categories",
            {"mappings": [{"category": "Pets", "group_name": "Animals"}]},
            ALICE,
            PERSONS,
        )


@pytest.mark.anyio
async def test_map_categories_resolves_group_ids() -> None:
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=_group_list_result(),
    ):
        result = await execute_tool(
            "map_categories",
            {"mappings": [{"category": "Pets", "group_name": "food & dining"}]},
            ALICE,
            PERSONS,
        )

    mapping = result["details"]["mappings"][0]
    assert mapping["group_id"] == str(FOOD_GROUP_ID)
    assert mapping["category"] == "<user_data>Pets</user_data>"


@pytest.mark.anyio
async def test_finalize_period_already_finalized_raises() -> None:
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            new_callable=AsyncMock,
            return_value=_settle_data(is_finalized=True),
        ),
        pytest.raises(ToolExecutionError, match="already finalized"),
    ):
        await execute_tool(
            "finalize_period", {"year": 2026, "month": 3}, ALICE, PERSONS
        )


@pytest.mark.anyio
async def test_finalize_period_surfaces_advisory_warnings() -> None:
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=_settle_data(warnings=["No upload from Bob"]),
    ):
        result = await execute_tool(
            "finalize_period", {"year": 2026, "month": 3}, ALICE, PERSONS
        )

    assert result["status"] == "pending_confirmation"
    assert result["details"]["warnings"] == ["No upload from Bob"]
    assert result["details"]["transaction_count"] == 82


@pytest.mark.anyio
async def test_unfinalize_period_not_finalized_raises() -> None:
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            new_callable=AsyncMock,
            return_value=(False, None),
        ),
        pytest.raises(ToolExecutionError, match="not finalized"),
    ):
        await execute_tool(
            "unfinalize_period", {"year": 2026, "month": 3}, ALICE, PERSONS
        )


@pytest.mark.anyio
async def test_record_settlement_unknown_person_lists_couple() -> None:
    with pytest.raises(ToolExecutionError, match="The couple is: Alice, Bob"):
        await execute_tool(
            "record_settlement",
            {"from_person": "Carol", "to_person": "Bob", "amount": 100},
            ALICE,
            PERSONS,
        )


@pytest.mark.anyio
async def test_record_settlement_returns_pending_with_annotation() -> None:
    result = await execute_tool(
        "record_settlement",
        {
            "from_person": "alice",
            "to_person": "Bob",
            "amount": 147.5,
            "method": "Venmo",
            "year": 2026,
            "month": 3,
        },
        ALICE,
        PERSONS,
    )

    assert result["status"] == "pending_confirmation"
    details = result["details"]
    assert details["from_person_id"] == str(ALICE.id)
    assert details["to_person_id"] == str(BOB.id)
    assert details["recorded_against"] == "2026-03"
    assert "$147.50 from Alice to Bob via Venmo" in str(result["description"])


@pytest.mark.anyio
async def test_waive_settlement_nothing_outstanding_raises() -> None:
    from decimal import Decimal

    from src.domain.ledger import SettlementLedger

    ledger = SettlementLedger(
        outstanding=None,
        months=(),
        payments=(),
        unapplied_payment_total=Decimal(0),
        span=None,
    )
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            new_callable=AsyncMock,
            return_value=ledger,
        ),
        pytest.raises(ToolExecutionError, match="nothing to waive"),
    ):
        await execute_tool("waive_settlement", {}, ALICE, PERSONS)


@pytest.mark.anyio
async def test_waive_settlement_captures_direction() -> None:
    from decimal import Decimal

    from src.domain.ledger import SettlementLedger
    from src.domain.reconciliation import SettlementResult

    ledger = SettlementLedger(
        outstanding=SettlementResult(
            amount=Decimal("321.00"),
            from_person_id=BOB.id,
            to_person_id=ALICE.id,
        ),
        months=(),
        payments=(),
        unapplied_payment_total=Decimal(0),
        span=((2026, 2), (2026, 3)),
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=ledger,
    ):
        result = await execute_tool("waive_settlement", {}, ALICE, PERSONS)

    details = result["details"]
    assert details["from_person_id"] == str(BOB.id)
    assert details["to_person_id"] == str(ALICE.id)
    assert details["covers"] == "2026-02 to 2026-03"
    assert "Bob owes Alice" in str(result["description"])


@pytest.mark.anyio
async def test_manage_settlement_merchant_remove_unknown_lists_configured() -> None:
    from src.application.use_cases.list_settlement_merchants import (
        ListSettlementMerchantsResult,
    )
    from tests.fixtures.factories import make_settlement_merchant

    merchants = ListSettlementMerchantsResult(
        merchants=[make_settlement_merchant(name="Venmo")]
    )
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            new_callable=AsyncMock,
            return_value=merchants,
        ),
        pytest.raises(ToolExecutionError, match="Configured: Venmo"),
    ):
        await execute_tool(
            "manage_settlement_merchant",
            {"action": "remove", "name": "Wise"},
            ALICE,
            PERSONS,
        )


@pytest.mark.anyio
async def test_manage_settlement_merchant_add_duplicate_raises() -> None:
    from src.application.use_cases.list_settlement_merchants import (
        ListSettlementMerchantsResult,
    )
    from tests.fixtures.factories import make_settlement_merchant

    merchants = ListSettlementMerchantsResult(
        merchants=[make_settlement_merchant(name="Venmo")]
    )
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            new_callable=AsyncMock,
            return_value=merchants,
        ),
        pytest.raises(ToolExecutionError, match="already exists"),
    ):
        await execute_tool(
            "manage_settlement_merchant",
            {"action": "add", "name": "venmo", "pattern": "venmo"},
            ALICE,
            PERSONS,
        )
