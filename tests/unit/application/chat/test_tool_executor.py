"""Tests for the chat tool executor.

Strategy: mock execute_use_case so each tool handler runs against
controlled return values without needing a real database.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import uuid

from attrs import evolve
import pytest

from src.application.chat.registry import execute_tool
from src.application.chat.tool_executor import handle_search_transactions
from src.application.use_cases._shared.upload_status import UploadStatus
from src.application.use_cases.get_budget_overview import GetBudgetOverviewResult
from src.application.use_cases.get_dashboard import (
    GetDashboardResult,
    MonthHistoryEntry,
)
from src.application.use_cases.get_settle_up_data import GetSettleUpDataResult
from src.application.use_cases.get_spending_trends import (
    GetSpendingTrendsResult,
    GetSpendingTrendsUseCase,
)
from src.application.use_cases.search_transactions import (
    SearchTransactionsResult,
    SearchTransactionsUseCase,
)
from src.domain.budget import BudgetOverview, CategoryGroupBudgetStatus
from src.domain.categories import CategoryGroupBreakdown
from src.domain.exceptions import ToolExecutionError, ValidationError
from src.domain.insights import SpendingFlow, SpendingTrends
from src.domain.ledger import (
    LedgerMonth,
    LedgerYear,
    MonthSettlementStatus,
    empty_ledger_year,
)
from src.domain.reconciliation import (
    PersonSummary,
    ReconciliationSummary,
    SettlementResult,
)
from tests.fixtures.factories import ALICE, BOB, make_transaction
from tests.fixtures.fake_llm_client import make_tool_context
from tests.fixtures.mocks import make_mock_uow

PERSONS = [ALICE, BOB]
CTX = make_tool_context(ALICE, PERSONS)


def _settle_result(
    *, owed_amount: Decimal = Decimal("147.50"), finalized: bool = False
) -> GetSettleUpDataResult:
    owed = SettlementResult(
        amount=owed_amount,
        from_person_id=ALICE.id,
        to_person_id=BOB.id,
    )
    return GetSettleUpDataResult(
        year=2026,
        month=3,
        years=[
            LedgerYear(
                year=2026,
                charged=owed,
                paid=None,
                balance=owed,
                span=((2026, 3), (2026, 3)),
            )
        ],
        months=[
            LedgerMonth(
                year=2026,
                month=3,
                charged=owed,
                paid=None,
                balance=owed,
                status=MonthSettlementStatus.CARRIED_FORWARD,
                runs_against_year=False,
            )
        ],
        settlements=[],
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
            CTX,
        )

    assert result["charged"] == {
        "amount": pytest.approx(147.50),
        "from": "Alice",
        "to": "Bob",
    }
    assert result["balance"] == {
        "amount": pytest.approx(147.50),
        "from": "Alice",
        "to": "Bob",
    }
    assert result["is_finalized"] is False
    assert len(result["uploads"]) == 2


@pytest.mark.asyncio
async def test_settlement_balance_swung_month_names_reversed_debtor() -> None:
    # Gross: Alice owes Bob $50; Alice paid $60 → balance: Bob owes Alice $10.
    from attrs import evolve

    base = _settle_result(owed_amount=Decimal("50.00"))
    swung_balance = SettlementResult(
        amount=Decimal("10.00"),
        from_person_id=BOB.id,
        to_person_id=ALICE.id,
    )
    swung = evolve(
        base,
        months=[
            evolve(
                base.months[0],
                balance=swung_balance,
                status=MonthSettlementStatus.PARTIALLY_SETTLED,
            )
        ],
    )

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=swung,
    ):
        result = await execute_tool(
            "get_settlement_balance",
            {"year": 2026, "month": 3},
            CTX,
        )

    assert result["charged"]["from"] == "Alice"
    assert result["balance"] == {
        "amount": pytest.approx(10.0),
        "from": "Bob",
        "to": "Alice",
    }


@pytest.mark.asyncio
async def test_settlement_balance_month_includes_status_and_year() -> None:
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=_settle_result(),
    ):
        result = await execute_tool(
            "get_settlement_balance",
            {"year": 2026, "month": 3},
            CTX,
        )

    assert result["status"] == "carried_forward"
    assert result["paid"] is None
    assert result["year_balance"] == {
        "amount": pytest.approx(147.50),
        "from": "Alice",
        "to": "Bob",
    }


@pytest.mark.asyncio
async def test_settlement_balance_without_month_returns_outstanding() -> None:
    from src.domain.ledger import SettlementLedger

    ledger = SettlementLedger(
        outstanding=SettlementResult(
            amount=Decimal("842.00"),
            from_person_id=ALICE.id,
            to_person_id=BOB.id,
        ),
        span=((2026, 3), (2026, 5)),
        months=(),
        years=(),
        settlements=(),
    )

    # _outstanding_balance_summary's inner loader returns the ledger directly.
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=ledger,
    ):
        result = await execute_tool("get_settlement_balance", {}, CTX)

    assert result["scope"] == "all_months"
    assert result["outstanding"] == {
        "amount": pytest.approx(842.0),
        "from": "Alice",
        "to": "Bob",
    }
    assert result["outstanding_span"] == {"start": "2026-03", "end": "2026-05"}
    assert result["remaining_balance"] == pytest.approx(842.0)
    assert result["net_from"] == "Alice"
    assert result["net_to"] == "Bob"


@pytest.mark.asyncio
async def test_settlement_balance_without_month_all_settled() -> None:
    from src.domain.ledger import SettlementLedger

    ledger = SettlementLedger(
        outstanding=None,
        span=None,
        months=(),
        years=(),
        settlements=(),
    )

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=ledger,
    ):
        result = await execute_tool("get_settlement_balance", {}, CTX)

    assert result["outstanding"] is None
    assert result["outstanding_span"] is None
    assert result["remaining_balance"] == pytest.approx(0.0)
    assert "settled" in str(result["status"])


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_input", [{"year": 2026}, {"month": 3}])
async def test_settlement_balance_partial_period_raises(
    tool_input: dict[str, object],
) -> None:
    """Only one of year/month is an ambiguous request — reject it."""
    with pytest.raises(
        ToolExecutionError, match="year and month must be provided together"
    ):
        await execute_tool("get_settlement_balance", tool_input, CTX)


@pytest.mark.asyncio
async def test_settlement_balance_no_charges() -> None:
    from attrs import evolve

    result_no_charges = evolve(_settle_result(), months=[], years=[])

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=result_no_charges,
    ):
        result = await execute_tool(
            "get_settlement_balance",
            {"year": 2026, "month": 3},
            CTX,
        )

    assert result["charged"] is None
    assert result["balance"] is None
    assert result["note"] == "No settlement-relevant charges this month"


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
            CTX,
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
            CTX,
        )

    assert result["finalization_warnings"] == ["3 unmapped categories"]


@pytest.mark.asyncio
async def test_unknown_tool_raises() -> None:
    with pytest.raises(ToolExecutionError, match="Unknown tool"):
        await execute_tool("nonexistent_tool", {}, CTX)


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
            CTX,
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
            CTX,
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
            CTX,
        )

    assert result["total_count"] == 1
    assert result["showing"] == 1
    assert result["scope"] == "all"
    tx = result["transactions"][0]
    assert tx["merchant"] == "Whole Foods"
    assert tx["category"] == "Groceries"
    assert tx["payer"] == "Alice"
    assert "id" in tx


async def _run_factory_with_stub_uow(factory):
    """Runs the lambda `execute_use_case` normally receives, against a stub
    uow — safe here because these tests patch `SearchTransactionsUseCase.execute`
    directly, so the uow itself is never touched."""
    return await factory(None)


@pytest.mark.asyncio
async def test_search_transactions_default_scope_is_all() -> None:
    mock_execute = AsyncMock(
        return_value=SearchTransactionsResult(transactions=[], total_count=0)
    )
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            side_effect=_run_factory_with_stub_uow,
        ),
        patch.object(SearchTransactionsUseCase, "execute", mock_execute),
    ):
        await execute_tool("search_transactions", {"year": 2026, "month": 3}, CTX)

    command = mock_execute.call_args.args[0]
    assert command.scope == "all"
    assert command.person_id is None


@pytest.mark.asyncio
async def test_search_transactions_household_scope() -> None:
    mock_execute = AsyncMock(
        return_value=SearchTransactionsResult(transactions=[], total_count=0)
    )
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            side_effect=_run_factory_with_stub_uow,
        ),
        patch.object(SearchTransactionsUseCase, "execute", mock_execute),
    ):
        await execute_tool(
            "search_transactions",
            {"year": 2026, "month": 3, "scope": "household"},
            CTX,
        )

    command = mock_execute.call_args.args[0]
    assert command.scope == "household"


@pytest.mark.asyncio
async def test_search_transactions_personal_scope_uses_current_user() -> None:
    mock_execute = AsyncMock(
        return_value=SearchTransactionsResult(transactions=[], total_count=0)
    )
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            side_effect=_run_factory_with_stub_uow,
        ),
        patch.object(SearchTransactionsUseCase, "execute", mock_execute),
    ):
        await execute_tool(
            "search_transactions",
            {"year": 2026, "month": 3, "scope": "personal"},
            CTX,
        )

    command = mock_execute.call_args.args[0]
    assert command.scope == "personal"
    assert command.person_id == ALICE.id


@pytest.mark.asyncio
async def test_search_transactions_unknown_group_raises() -> None:
    """An unknown category_group is an error naming the valid groups —
    never a silent unfiltered search."""
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            new_callable=AsyncMock,
            return_value=_category_groups_result(),
        ),
        pytest.raises(
            ToolExecutionError,
            match=r"Unknown category group: Pets\. Valid groups: Food & Dining",
        ),
    ):
        await execute_tool(
            "search_transactions",
            {"year": 2026, "month": 3, "category_group": "Pets"},
            CTX,
        )


@pytest.mark.asyncio
async def test_bulk_update_transactions_rejects_unknown_category() -> None:
    """Propose-time validation — a typo'd category is rejected before the
    confirmation card is even shown, mirroring the confirm-time re-check
    in confirmed_actions._exec_bulk."""
    tx = make_transaction()
    uow = make_mock_uow()
    uow.transactions.get_by_ids.return_value = [tx]
    uow.categories.get_by_name.return_value = None

    async def run_with_mock_uow(factory):
        return await factory(uow)

    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            side_effect=run_with_mock_uow,
        ),
        pytest.raises(ToolExecutionError, match="Unknown category"),
    ):
        await execute_tool(
            "bulk_update_transactions",
            {
                "transaction_ids": [str(tx.id)],
                "changes": {"category": "Bogus"},
            },
            CTX,
        )


# --- v1.8.1 read tools ---


def _recon_summary(**overrides: object) -> ReconciliationSummary:
    base = ReconciliationSummary(
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        total_household_spending=Decimal("1200.00"),
        total_household_refunds=Decimal("50.00"),
        net_household_spending=Decimal("1150.00"),
        person_summaries=[
            PersonSummary(
                person_id=ALICE.id,
                total_paid=Decimal("700.00"),
                total_share=Decimal("575.00"),
            ),
            PersonSummary(
                person_id=BOB.id,
                total_paid=Decimal("450.00"),
                total_share=Decimal("575.00"),
            ),
        ],
        settlement=SettlementResult(
            amount=Decimal("125.00"),
            from_person_id=BOB.id,
            to_person_id=ALICE.id,
        ),
        category_group_breakdowns=[
            CategoryGroupBreakdown(
                group_id=uuid.uuid4(),
                group_name="Food & Dining",
                total_amount=Decimal("-800.00"),
                transaction_count=12,
                categories=[],
            )
        ],
        transaction_count=42,
        split_transactions=[],
        category_lookup={},
    )
    return evolve(base, **overrides)


@pytest.mark.asyncio
async def test_get_tags_wraps_and_truncates() -> None:
    from src.application.use_cases.get_tags import GetTagsResult

    tags = [f"tag{i}" for i in range(25)]
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=GetTagsResult(tags=tags),
    ):
        result = await execute_tool("get_tags", {}, CTX)

    assert result["total_count"] == 25
    assert result["showing"] == 20
    assert result["tags"][0] == "tag0"


@pytest.mark.asyncio
async def test_get_tags_empty() -> None:
    from src.application.use_cases.get_tags import GetTagsResult

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=GetTagsResult(tags=[]),
    ):
        result = await execute_tool("get_tags", {}, CTX)

    assert result == {"total_count": 0, "showing": 0, "tags": []}


@pytest.mark.asyncio
async def test_get_transaction_history_happy_path() -> None:
    from datetime import UTC, datetime

    from src.application.use_cases.get_transaction_edits import (
        GetTransactionEditsResult,
    )
    from src.domain.entities.import_event import ImportEvent
    from tests.fixtures.factories import make_transaction_edit

    tx_id = uuid.uuid4()
    edit = make_transaction_edit(
        transaction_id=tx_id,
        old_value="Dining Out",
        new_value="Fast Food",
        edited_by_person_id=BOB.id,
    )
    history = GetTransactionEditsResult(
        edits=[edit],
        import_event=ImportEvent(
            person_id=ALICE.id, imported_at=datetime(2026, 3, 2, tzinfo=UTC)
        ),
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=history,
    ):
        result = await execute_tool(
            "get_transaction_history", {"transaction_id": str(tx_id)}, CTX
        )

    assert result["total_count"] == 1
    entry = result["edits"][0]
    assert entry["field"] == "category"
    assert entry["old_value"] == "Dining Out"
    assert entry["new_value"] == "Fast Food"
    assert entry["edited_by"] == "Bob"
    assert result["imported"] == {"by": "Alice", "at": "2026-03-02T00:00:00+00:00"}


@pytest.mark.asyncio
async def test_get_transaction_history_rejects_bad_uuid() -> None:
    with pytest.raises(ToolExecutionError, match="Invalid transaction ID"):
        await execute_tool("get_transaction_history", {"transaction_id": "nope"}, CTX)


def _category_groups_result() -> object:
    from src.application.use_cases.list_category_groups import (
        CategoryGroupWithCategories,
        ListCategoryGroupsResult,
    )
    from tests.fixtures.factories import make_category, make_category_group

    food = make_category_group(name="Food & Dining")
    transfer = make_category_group(name="Transfer", kind="transfer")
    return ListCategoryGroupsResult(
        items=[
            CategoryGroupWithCategories(
                group=food,
                categories=[
                    make_category(
                        name="Groceries", group_id=food.id, include_personal=True
                    ),
                    make_category(name="Dining Out", group_id=food.id),
                ],
            ),
            CategoryGroupWithCategories(
                group=transfer,
                categories=[
                    make_category(name="Credit Card Payment", group_id=transfer.id)
                ],
            ),
        ]
    )


@pytest.mark.asyncio
async def test_get_budgets_filters_and_resolves_group_names() -> None:
    from src.application.use_cases.list_budgets import ListBudgetsResult
    from tests.fixtures.factories import make_category_group_budget

    groups = _category_groups_result()
    group_id = groups.items[0].group.id
    budgets = ListBudgetsResult(
        budgets=[
            make_category_group_budget(
                group_id=group_id, monthly_amount=Decimal("700.00"), month=3
            ),
            make_category_group_budget(
                group_id=group_id,
                monthly_amount=Decimal("100.00"),
                month=3,
                person_id=ALICE.id,
            ),
            make_category_group_budget(group_id=group_id, month=4),
            make_category_group_budget(group_id=group_id, month=3, year=2025),
        ]
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        side_effect=[budgets, groups],
    ):
        result = await execute_tool("get_budgets", {"year": 2026, "month": 3}, CTX)

    assert result["total_count"] == 2
    assert {row["scope"] for row in result["budgets"]} == {"household", "personal"}
    assert result["budgets"][0]["group"] == "Food & Dining"
    assert result["budgets"][0]["amount"] == pytest.approx(700.0)


@pytest.mark.asyncio
async def test_get_budgets_scope_household_only() -> None:
    from src.application.use_cases.list_budgets import ListBudgetsResult
    from tests.fixtures.factories import make_category_group_budget

    groups = _category_groups_result()
    group_id = groups.items[0].group.id
    budgets = ListBudgetsResult(
        budgets=[
            make_category_group_budget(group_id=group_id, month=3),
            make_category_group_budget(group_id=group_id, month=3, person_id=ALICE.id),
        ]
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        side_effect=[budgets, groups],
    ):
        result = await execute_tool(
            "get_budgets",
            {"year": 2026, "month": 3, "scope": "household"},
            CTX,
        )

    assert result["total_count"] == 1
    assert result["budgets"][0]["scope"] == "household"


@pytest.mark.asyncio
async def test_get_category_setup_happy_path() -> None:
    from src.application.use_cases.list_unmapped_categories import (
        ListUnmappedCategoriesResult,
    )

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        side_effect=[
            _category_groups_result(),
            ListUnmappedCategoriesResult(categories=["Mystery"]),
        ],
    ):
        result = await execute_tool("get_category_setup", {}, CTX)

    group = result["groups"][0]
    assert group["group"] == "Food & Dining"
    assert group["kind"] == "expense"
    assert "Groceries" in group["categories"]
    assert result["groups"][1]["kind"] == "transfer"
    assert result["include_personal_categories"] == ["Groceries"]
    assert result["unmapped_categories"] == ["Mystery"]


@pytest.mark.asyncio
async def test_get_upload_history_newest_first_with_limit() -> None:
    from datetime import UTC, date, datetime

    from src.application.use_cases.get_upload_history import (
        GetUploadHistoryResult,
        UploadHistoryEntry,
    )

    def entry(day: int) -> UploadHistoryEntry:
        return UploadHistoryEntry(
            upload_id=uuid.uuid4(),
            person_id=ALICE.id,
            person_name="Alice",
            filename=f"march-{day}.csv",
            uploaded_at=datetime(2026, 3, day, tzinfo=UTC),
            transaction_count=40 + day,
            household_count=20,
            date_range_start=date(2026, 3, 1),
            date_range_end=date(2026, 3, 31),
        )

    history = GetUploadHistoryResult(entries=[entry(1), entry(5), entry(3)])
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=history,
    ):
        result = await execute_tool("get_upload_history", {"limit": 2}, CTX)

    assert result["total_count"] == 3
    assert result["showing"] == 2
    uploads = result["uploads"]
    assert uploads[0]["filename"] == "march-5.csv"
    assert uploads[1]["filename"] == "march-3.csv"
    assert uploads[0]["covers"] == "2026-03-01 to 2026-03-31"


@pytest.mark.asyncio
async def test_get_reconciliation_report_concise() -> None:
    from src.application.use_cases.get_reconciliation import GetReconciliationResult

    recon = GetReconciliationResult(
        summary=_recon_summary(),
        transactions=[],
        upload_statuses=[],
        unmapped_categories=[],
        persons=PERSONS,
        is_finalized=False,
        finalized_at=None,
        year=2026,
        month=3,
        latest_transaction_month=(2026, 3),
        spending_transactions=[],
        category_kinds={},
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=recon,
    ):
        result = await execute_tool(
            "get_reconciliation_report", {"year": 2026, "month": 3}, CTX
        )

    assert result["month"] == "2026-03"
    assert result["net_household_spending"] == pytest.approx(1150.0)
    assert result["gross_settlement"] == {
        "amount": pytest.approx(125.0),
        "from": "Bob",
        "to": "Alice",
    }
    assert result["persons"][0] == {
        "name": "Alice",
        "paid": pytest.approx(700.0),
        "fair_share": pytest.approx(575.0),
    }
    assert "group_breakdown" not in result
    assert "largest_transactions" not in result
    assert "unmapped_categories" not in result


@pytest.mark.asyncio
async def test_get_reconciliation_report_detailed_adds_breakdown_and_rows() -> None:
    from src.application.use_cases.get_reconciliation import GetReconciliationResult

    txns = [
        make_transaction(merchant=f"Store {i}", amount=Decimal(f"-{10 + i}"))
        for i in range(25)
    ]
    recon = GetReconciliationResult(
        summary=_recon_summary(),
        transactions=txns,
        upload_statuses=[],
        unmapped_categories=["Mystery"],
        persons=PERSONS,
        is_finalized=False,
        finalized_at=None,
        year=2026,
        month=3,
        latest_transaction_month=(2026, 3),
        spending_transactions=txns,
        category_kinds={},
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=recon,
    ):
        result = await execute_tool(
            "get_reconciliation_report",
            {"year": 2026, "month": 3, "response_format": "detailed"},
            CTX,
        )

    assert result["group_breakdown"][0]["group"] == "Food & Dining"
    largest = result["largest_transactions"]
    assert len(largest) == 20
    # Sorted by |amount| descending — Store 24 (-34) first.
    assert largest[0]["merchant"] == "Store 24"
    assert result["unmapped_categories"] == ["Mystery"]


@pytest.mark.asyncio
async def test_get_reconciliation_report_largest_lists_spending_rows_only() -> None:
    """The row list agrees with the totals: transfers, excluded rows, and
    linked settlement legs never rank as the largest transaction."""
    from src.application.use_cases.get_reconciliation import GetReconciliationResult

    listed = [
        make_transaction(
            merchant="Chase", amount=Decimal(-5000), category="Credit Card Payment"
        ),
        make_transaction(merchant="Venmo", amount=Decimal(-1981), is_settlement=True),
        make_transaction(merchant="Refund me", amount=Decimal(-900), is_excluded=True),
        make_transaction(merchant="Whole Foods", amount=Decimal(-120)),
    ]
    recon = GetReconciliationResult(
        summary=_recon_summary(),
        transactions=listed,
        upload_statuses=[],
        unmapped_categories=[],
        persons=PERSONS,
        is_finalized=False,
        finalized_at=None,
        year=2026,
        month=3,
        latest_transaction_month=(2026, 3),
        spending_transactions=[
            t for t in listed if t.category != "Credit Card Payment"
        ],
        category_kinds={"Credit Card Payment": "transfer"},
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=recon,
    ):
        result = await execute_tool(
            "get_reconciliation_report",
            {"year": 2026, "month": 3, "response_format": "detailed"},
            CTX,
        )

    assert [r["merchant"] for r in result["largest_transactions"]] == ["Whole Foods"]


def _ledger_settlement_record() -> object:
    from src.application.use_cases._shared.settlement_math import (
        LedgerSettlementRecord,
    )
    from src.application.use_cases._shared.settlement_records import SettlementRecord
    from src.domain.ledger import LedgerSettlement, PortionPlan
    from tests.fixtures.factories import make_settlement

    linked_tx = uuid.uuid4()
    settlement = make_settlement(
        from_person_id=ALICE.id,
        to_person_id=BOB.id,
        amount=Decimal("147.50"),
        notes="rent catch-up",
    )
    return LedgerSettlementRecord(
        record=SettlementRecord(
            settlement=settlement,
            linked_transaction_ids=[linked_tx],
        ),
        application=LedgerSettlement(
            settlement_id=settlement.id,
            portions=(PortionPlan(year=2026, month=3, amount=Decimal("147.50")),),
        ),
    )


@pytest.mark.asyncio
async def test_get_settlement_activity_with_outstanding_fetches_candidates() -> None:
    from attrs import evolve

    from src.application.use_cases.find_settlement_candidates import (
        FindSettlementCandidatesResult,
    )
    from src.application.use_cases.list_settlement_merchants import (
        ListSettlementMerchantsResult,
    )
    from src.domain.settlement_matching import SettlementCandidate
    from tests.fixtures.factories import make_settlement_merchant

    settle = evolve(_settle_result(), settlements=[_ledger_settlement_record()])
    merchants = ListSettlementMerchantsResult(
        merchants=[make_settlement_merchant(name="Venmo", merchant_pattern="venmo")]
    )
    candidate_tx = make_transaction(merchant="Venmo Payment", amount=Decimal("147.50"))
    candidates = FindSettlementCandidatesResult(
        candidates=[
            SettlementCandidate(
                transaction=candidate_tx,
                score=5,
                match_reasons=("amount match", "merchant match"),
            )
        ]
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        side_effect=[settle, merchants, candidates],
    ) as mock_execute:
        result = await execute_tool(
            "get_settlement_activity", {"year": 2026, "month": 3}, CTX
        )

    assert mock_execute.call_count == 3
    payment = result["settlements"][0]
    assert payment["from"] == "Alice"
    assert payment["notes"] == "rent catch-up"
    assert payment["portions"] == [{"month": "2026-03", "amount": pytest.approx(147.5)}]
    assert len(payment["linked_transaction_ids"]) == 1
    cand = result["candidate_transactions"][0]
    assert cand["merchant"] == "Venmo Payment"
    assert cand["score"] == 5
    assert result["settlement_merchants"] == [
        {
            "name": "Venmo",
            "pattern": "venmo",
        }
    ]


@pytest.mark.asyncio
async def test_get_settlement_activity_settled_skips_candidates() -> None:
    from attrs import evolve

    from src.application.use_cases.list_settlement_merchants import (
        ListSettlementMerchantsResult,
    )

    settle = evolve(_settle_result(), years=[], months=[])
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        side_effect=[settle, ListSettlementMerchantsResult(merchants=[])],
    ) as mock_execute:
        result = await execute_tool(
            "get_settlement_activity", {"year": 2026, "month": 3}, CTX
        )

    assert mock_execute.call_count == 2
    assert result["year_balance"] is None
    assert result["candidate_transactions"] == []


def _dashboard_result(**overrides: object) -> GetDashboardResult:
    base = GetDashboardResult(
        scope="household",
        current_person_id=None,
        current_month=_recon_summary(),
        upload_statuses=[],
        household_spending_month=Decimal("1150.00"),
        household_spending_ytd=Decimal("3400.00"),
        ytd_settlement=None,
        ytd_net_settlement=None,
        ytd_total_settled=Decimal("500.00"),
        settlement_year=empty_ledger_year(2026),
        outstanding_balance=SettlementResult(
            amount=Decimal("147.50"),
            from_person_id=ALICE.id,
            to_person_id=BOB.id,
        ),
        outstanding_span=((2026, 2), (2026, 3)),
        month_history=[
            MonthHistoryEntry(
                year=2026,
                month=2,
                total_household_spending=Decimal("1000.00"),
                settlement_amount=Decimal("200.00"),
                settlement_remaining=Decimal("50.00"),
                settlement_from_person_id=ALICE.id,
                settlement_to_person_id=BOB.id,
                is_finalized=True,
                is_settled=False,
                settlement_status="partially_settled",
                settled_at=None,
            )
        ],
        persons=PERSONS,
        unmapped_categories=["Mystery"],
        is_finalized=False,
        finalized_at=None,
    )
    return evolve(base, **overrides)


@pytest.mark.asyncio
async def test_get_dashboard_summary_household() -> None:
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=_dashboard_result(),
    ):
        result = await execute_tool("get_dashboard_summary", {"year": 2026}, CTX)

    assert result["household_spending_ytd"] == pytest.approx(3400.0)
    assert result["outstanding"]["from"] == "Alice"
    assert result["unmapped_category_count"] == 1
    row = result["month_history"][0]
    assert row["month"] == "2026-02"
    assert row["settlement_status"] == "partially_settled"
    assert row["settlement_remaining"] == pytest.approx(50.0)
    assert "my_spending_month" not in result


@pytest.mark.asyncio
async def test_get_dashboard_summary_personal_adds_my_fields() -> None:
    dashboard = _dashboard_result(
        scope="personal",
        current_person_id=ALICE.id,
        my_spending_month=Decimal("400.00"),
        my_household_share_month=Decimal("575.00"),
        my_personal_spending_month=Decimal("125.00"),
        my_spending_ytd=Decimal("1200.00"),
    )
    from src.application.use_cases.get_dashboard import GetDashboardUseCase

    mock_execute = AsyncMock(return_value=dashboard)
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            side_effect=_run_factory_with_stub_uow,
        ),
        patch.object(GetDashboardUseCase, "execute", mock_execute),
    ):
        result = await execute_tool(
            "get_dashboard_summary",
            {"year": 2026, "scope": "personal"},
            CTX,
        )

    command = mock_execute.call_args.args[0]
    assert command.person_id == ALICE.id
    assert result["my_spending_month"] == pytest.approx(400.0)
    assert result["my_spending_ytd"] == pytest.approx(1200.0)


@pytest.mark.asyncio
async def test_get_adjustments_preview_happy_path() -> None:
    from datetime import date

    from src.application.use_cases.export_adjustments import PreviewAdjustmentsResult
    from src.domain.export.adjustments import Adjustment

    preview = PreviewAdjustmentsResult(
        adjustments=[
            Adjustment(
                dedup_id="adj-1",
                source_transaction_id=uuid.uuid4(),
                date=date(2026, 3, 14),
                merchant="Whole Foods",
                category="Groceries",
                amount=Decimal("-41.71"),
                account="Adjustments",
            )
        ],
        person_name="Alice",
        adjustment_count=1,
    )
    from src.application.use_cases.export_adjustments import PreviewAdjustmentsUseCase

    mock_execute = AsyncMock(return_value=preview)
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            side_effect=_run_factory_with_stub_uow,
        ),
        patch.object(PreviewAdjustmentsUseCase, "execute", mock_execute),
    ):
        result = await execute_tool(
            "get_adjustments_preview", {"year": 2026, "month": 3}, CTX
        )

    command = mock_execute.call_args.args[0]
    assert command.person_id == ALICE.id
    assert result["person"] == "Alice"
    assert result["total_count"] == 1
    row = result["adjustments"][0]
    assert row["merchant"] == "Whole Foods"
    assert row["account"] == "Adjustments"
    assert row["amount"] == pytest.approx(-41.71)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_input", "expected_person_id"),
    [
        ({"year": 2026}, None),
        ({"year": 2026, "scope": "household"}, None),
        ({"year": 2026, "scope": "personal"}, ALICE.id),
    ],
)
async def test_spending_trends_scope_resolves_current_user(
    tool_input: dict[str, object], expected_person_id: uuid.UUID | None
) -> None:
    mock_execute = AsyncMock(
        return_value=GetSpendingTrendsResult(
            year=2026,
            month=3,
            trends=SpendingTrends(
                monthly_group_spending=[], monthly_totals=[], group_summaries=[]
            ),
            comparison_cards=[],
            category_comparisons=[],
            month_flow=SpendingFlow([], [], []),
            ytd_flow=SpendingFlow([], [], []),
            persons=PERSONS,
        )
    )
    with (
        patch(
            "src.application.chat.tool_executor.execute_use_case",
            side_effect=_run_factory_with_stub_uow,
        ),
        patch.object(GetSpendingTrendsUseCase, "execute", mock_execute),
    ):
        result = await execute_tool("get_spending_trends", tool_input, CTX)

    command = mock_execute.call_args.args[0]
    assert command.person_id == expected_person_id
    assert result["scope"] == command.scope


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["get_spending_trends", "get_budget_overview"])
async def test_person_scoped_tools_reject_unknown_scope(tool: str) -> None:
    """`all` is a valid scope for sibling tools but not here — it must fail
    loudly instead of silently running the household lens."""
    with pytest.raises(ToolExecutionError, match="scope must be"):
        await execute_tool(tool, {"year": 2026, "month": 3, "scope": "all"}, CTX)


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["mine", ["household"]])
async def test_search_transactions_rejects_unknown_scope(scope: object) -> None:
    """An off-enum scope must fail loudly rather than silently searching the
    default lens and echoing the bogus label back. A non-string (list) input
    is rejected the same way, not with a TypeError."""
    with pytest.raises(ValidationError, match="scope must be"):
        await handle_search_transactions(
            {"year": 2026, "month": 3, "scope": scope}, CTX
        )
