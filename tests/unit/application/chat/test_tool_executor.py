"""Tests for the chat tool executor.

Strategy: mock execute_use_case so each tool handler runs against
controlled return values without needing a real database.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from src.application.chat.tool_executor import execute_tool
from src.application.use_cases._shared.upload_status import UploadStatus
from src.application.use_cases.get_budget_overview import GetBudgetOverviewResult
from src.application.use_cases.get_settle_up_data import GetSettleUpDataResult
from src.application.use_cases.search_transactions import SearchTransactionsResult
from src.domain.budget import BudgetOverview, CategoryGroupBudgetStatus
from src.domain.exceptions import ToolExecutionError
from src.domain.reconciliation import SettlementResult
from tests.fixtures.factories import make_person, make_transaction

ALICE = make_person(name="Alice", id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
BOB = make_person(name="Bob", id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
PERSONS = [ALICE, BOB]


def _settle_result(
    *, owed_amount: Decimal = Decimal("147.50"), finalized: bool = False
) -> GetSettleUpDataResult:
    return GetSettleUpDataResult(
        year=2026,
        month=3,
        owed=SettlementResult(
            amount=owed_amount,
            from_person_id=ALICE.id,
            to_person_id=BOB.id,
        ),
        net_position=None,
        recorded_settlements=[],
        remaining_balance=owed_amount,
        upload_statuses=[
            UploadStatus(
                person_id=ALICE.id,
                person_name="Alice",
                has_uploaded=True,
                upload_count=47,
            ),
            UploadStatus(
                person_id=BOB.id, person_name="Bob", has_uploaded=True, upload_count=35
            ),
        ],
        persons=PERSONS,
        is_finalized=finalized,
        finalized_at=None,
        transaction_count=82,
        latest_transaction_month=(2026, 3),
        finalization_warnings=[],
        payer_splits=[],
        payer_group_splits=[],
    )


@pytest.mark.asyncio
async def test_settlement_balance_happy_path() -> None:
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=_settle_result(),
    ):
        result = await execute_tool(
            "get_settlement_balance",
            {"year": 2026, "month": 3},
            ALICE,
            PERSONS,
        )

    assert result["from"] == "Alice"
    assert result["to"] == "Bob"
    assert result["gross_amount"] == pytest.approx(147.50)
    assert result["is_finalized"] is False
    assert len(result["uploads"]) == 2


@pytest.mark.asyncio
async def test_settlement_balance_no_owed() -> None:
    no_owed = _settle_result()
    # Create a new result with owed=None
    from attrs import evolve

    result_no_owed = evolve(no_owed, owed=None)

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=result_no_owed,
    ):
        result = await execute_tool(
            "get_settlement_balance",
            {"year": 2026, "month": 3},
            ALICE,
            PERSONS,
        )

    assert result["gross_amount"] == pytest.approx(0.0)
    assert result["status"] == "No settlement needed this month"


@pytest.mark.asyncio
async def test_dashboard_status_happy_path() -> None:
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=_settle_result(),
    ):
        result = await execute_tool(
            "get_dashboard_status",
            {"year": 2026, "month": 3},
            ALICE,
            PERSONS,
        )

    assert result["is_finalized"] is False
    assert result["transaction_count"] == 82
    assert result["uploads"][0]["person"] == "Alice"
    assert result["uploads"][0]["uploaded"] is True
    assert result["finalization_warnings"] == []


@pytest.mark.asyncio
async def test_dashboard_status_includes_warnings() -> None:
    from attrs import evolve

    result_with_warnings = evolve(
        _settle_result(), finalization_warnings=["3 unmapped categories"]
    )

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=result_with_warnings,
    ):
        result = await execute_tool(
            "get_dashboard_status",
            {"year": 2026, "month": 3},
            ALICE,
            PERSONS,
        )

    assert result["finalization_warnings"] == ["3 unmapped categories"]


@pytest.mark.asyncio
async def test_unknown_tool_raises() -> None:
    with pytest.raises(ToolExecutionError, match="Unknown tool"):
        await execute_tool("nonexistent_tool", {}, ALICE, PERSONS)


@pytest.mark.asyncio
async def test_tool_execution_error_wraps_exception() -> None:
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            new_callable=AsyncMock,
            side_effect=ValueError("something broke"),
        ),
        pytest.raises(ToolExecutionError, match="something broke"),
    ):
        await execute_tool(
            "get_settlement_balance",
            {"year": 2026, "month": 3},
            ALICE,
            PERSONS,
        )


@pytest.mark.asyncio
async def test_budget_overview_happy_path() -> None:
    overview = BudgetOverview(
        year=2026,
        month=3,
        group_statuses=[
            CategoryGroupBudgetStatus(
                group_id=uuid.uuid4(),
                group_name="Food & Dining",
                budget_id=uuid.uuid4(),
                monthly_budget=Decimal("800.00"),
                monthly_spent=Decimal("742.00"),
                ytd_budget=Decimal("2400.00"),
                ytd_spent=Decimal("2100.00"),
                monthly_health="near_limit",
                ytd_health="on_track",
                average_monthly_spending=Decimal("700.00"),
                categories=[],
                budgeted_months=3,
            ),
        ],
        total_monthly_budget=Decimal("800.00"),
        total_monthly_spent=Decimal("742.00"),
        total_ytd_budget=Decimal("2400.00"),
        total_ytd_spent=Decimal("2100.00"),
    )
    budget_result = GetBudgetOverviewResult(
        overview=overview,
        budgets=[],
        categories=[],
        persons=PERSONS,
    )

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=budget_result,
    ):
        result = await execute_tool(
            "get_budget_overview",
            {"year": 2026, "month": 3},
            ALICE,
            PERSONS,
        )

    assert result["month"] == "2026-03"
    assert len(result["groups"]) == 1
    assert result["groups"][0]["name"] == "Food & Dining"
    assert result["groups"][0]["spent"] == pytest.approx(742.0)
    assert result["groups"][0]["budget"] == pytest.approx(800.0)
    assert result["total_spent"] == pytest.approx(742.0)


@pytest.mark.asyncio
async def test_search_transactions_happy_path() -> None:
    txns = [
        make_transaction(
            merchant="Whole Foods",
            amount=Decimal("-83.42"),
            category="Groceries",
            payer_person_id=ALICE.id,
            payer_percentage=50,
        ),
    ]

    search_result = SearchTransactionsResult(
        transactions=txns,
        total_count=1,
    )

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=search_result,
    ):
        result = await execute_tool(
            "search_transactions",
            {"year": 2026, "month": 3, "merchant": "Whole Foods"},
            ALICE,
            PERSONS,
        )

    assert result["total_count"] == 1
    assert result["showing"] == 1
    tx = result["transactions"][0]
    assert tx["merchant"] == "<user_data>Whole Foods</user_data>"
    assert tx["payer"] == "Alice"
    assert "id" in tx
