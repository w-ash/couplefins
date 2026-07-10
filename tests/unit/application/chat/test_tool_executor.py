"""Tests for the chat tool executor.

Strategy: mock execute_use_case so each tool handler runs against
controlled return values without needing a real database.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from src.application.chat.registry import execute_tool
from src.application.use_cases._shared.upload_status import UploadStatus
from src.application.use_cases.get_budget_overview import GetBudgetOverviewResult
from src.application.use_cases.get_settle_up_data import GetSettleUpDataResult
from src.application.use_cases.search_transactions import (
    SearchTransactionsResult,
    SearchTransactionsUseCase,
)
from src.domain.budget import BudgetOverview, CategoryGroupBudgetStatus
from src.domain.exceptions import ToolExecutionError
from src.domain.ledger import LedgerMonth, MonthSettlementStatus
from src.domain.reconciliation import SettlementResult
from tests.fixtures.factories import make_person, make_transaction
from tests.fixtures.mocks import make_mock_uow

ALICE = make_person(name="Alice", id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
BOB = make_person(name="Bob", id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
PERSONS = [ALICE, BOB]


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
        owed=owed,
        net_position=owed,
        recorded_settlements=[],
        remaining_balance=owed_amount,
        outstanding=owed,
        outstanding_span=((2026, 3), (2026, 3)),
        ledger_months=[
            LedgerMonth(
                year=2026,
                month=3,
                gross=owed,
                applied=Decimal(0),
                remaining=owed_amount,
                status=MonthSettlementStatus.CARRIED_FORWARD,
                covering_settlement_ids=(),
                is_offset=False,
            )
        ],
        all_settlements=[],
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
async def test_settlement_balance_overpayment_names_reversed_debtor() -> None:
    # Gross: Alice owes Bob $50; Alice paid $60 → net: Bob owes Alice $10.
    from attrs import evolve

    overpaid = evolve(
        _settle_result(owed_amount=Decimal("50.00")),
        net_position=SettlementResult(
            amount=Decimal("10.00"),
            from_person_id=BOB.id,
            to_person_id=ALICE.id,
        ),
        remaining_balance=Decimal("10.00"),
    )

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=overpaid,
    ):
        result = await execute_tool(
            "get_settlement_balance",
            {"year": 2026, "month": 3},
            ALICE,
            PERSONS,
        )

    assert result["from"] == "Alice"
    assert result["to"] == "Bob"
    assert result["net_from"] == "Bob"
    assert result["net_to"] == "Alice"
    assert result["remaining_balance"] == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_settlement_balance_month_includes_ledger_row() -> None:
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

    assert result["month_ledger"] == {
        "gross": pytest.approx(147.50),
        "applied": 0.0,
        "remaining": pytest.approx(147.50),
        "status": "carried_forward",
    }
    assert result["outstanding"] == {
        "amount": pytest.approx(147.50),
        "from": "Alice",
        "to": "Bob",
    }
    assert result["outstanding_span"] == {"start": "2026-03", "end": "2026-03"}


@pytest.mark.asyncio
async def test_settlement_balance_without_month_returns_outstanding() -> None:
    from src.domain.ledger import SettlementLedger

    ledger = SettlementLedger(
        outstanding=SettlementResult(
            amount=Decimal("842.00"),
            from_person_id=ALICE.id,
            to_person_id=BOB.id,
        ),
        months=(),
        payments=(),
        unapplied_payment_total=Decimal(0),
        span=((2026, 3), (2026, 5)),
    )

    # _outstanding_balance_summary's inner loader returns the ledger directly.
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=ledger,
    ):
        result = await execute_tool("get_settlement_balance", {}, ALICE, PERSONS)

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
        months=(),
        payments=(),
        unapplied_payment_total=Decimal(0),
        span=None,
    )

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=ledger,
    ):
        result = await execute_tool("get_settlement_balance", {}, ALICE, PERSONS)

    assert result["outstanding"] is None
    assert result["outstanding_span"] is None
    assert result["remaining_balance"] == pytest.approx(0.0)
    assert "settled" in str(result["status"])


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
    assert result["scope"] == "all"
    tx = result["transactions"][0]
    assert tx["merchant"] == "<user_data>Whole Foods</user_data>"
    assert tx["category"] == "<user_data>Groceries</user_data>"
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
        await execute_tool(
            "search_transactions", {"year": 2026, "month": 3}, ALICE, PERSONS
        )

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
            ALICE,
            PERSONS,
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
            ALICE,
            PERSONS,
        )

    command = mock_execute.call_args.args[0]
    assert command.scope == "personal"
    assert command.person_id == ALICE.id


@pytest.mark.asyncio
async def test_bulk_update_transactions_rejects_unknown_category() -> None:
    """Propose-time validation — a typo'd category is rejected before the
    confirmation card is even shown, mirroring the confirm-time re-check
    in confirmed_actions._exec_bulk."""
    tx = make_transaction()
    uow = make_mock_uow()
    uow.transactions.get_by_id.return_value = tx
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
            ALICE,
            PERSONS,
        )


# --- v1.8.1 read tools ---


def _recon_summary(**overrides: object) -> object:
    from datetime import date

    from src.domain.categories import CategoryGroupBreakdown
    from src.domain.reconciliation import PersonSummary, ReconciliationSummary

    defaults: dict[str, object] = {
        "start_date": date(2026, 3, 1),
        "end_date": date(2026, 3, 31),
        "total_household_spending": Decimal("1200.00"),
        "total_household_refunds": Decimal("50.00"),
        "net_household_spending": Decimal("1150.00"),
        "person_summaries": [
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
        "settlement": SettlementResult(
            amount=Decimal("125.00"),
            from_person_id=BOB.id,
            to_person_id=ALICE.id,
        ),
        "category_group_breakdowns": [
            CategoryGroupBreakdown(
                group_id=uuid.uuid4(),
                group_name="Food & Dining",
                total_amount=Decimal("-800.00"),
                transaction_count=12,
                categories=[],
            )
        ],
        "transaction_count": 42,
        "split_transactions": [],
        "category_lookup": {},
    }
    defaults.update(overrides)
    return ReconciliationSummary(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_tags_wraps_and_truncates() -> None:
    from src.application.use_cases.get_tags import GetTagsResult

    tags = [f"tag{i}" for i in range(25)]
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=GetTagsResult(tags=tags),
    ):
        result = await execute_tool("get_tags", {}, ALICE, PERSONS)

    assert result["total_count"] == 25
    assert result["showing"] == 20
    assert result["tags"][0] == "<user_data>tag0</user_data>"


@pytest.mark.asyncio
async def test_get_tags_empty() -> None:
    from src.application.use_cases.get_tags import GetTagsResult

    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=GetTagsResult(tags=[]),
    ):
        result = await execute_tool("get_tags", {}, ALICE, PERSONS)

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
            "get_transaction_history", {"transaction_id": str(tx_id)}, ALICE, PERSONS
        )

    assert result["total_count"] == 1
    entry = result["edits"][0]
    assert entry["field"] == "category"
    assert entry["old_value"] == "<user_data>Dining Out</user_data>"
    assert entry["new_value"] == "<user_data>Fast Food</user_data>"
    assert entry["edited_by"] == "Bob"
    assert result["imported"] == {"by": "Alice", "at": "2026-03-02T00:00:00+00:00"}


@pytest.mark.asyncio
async def test_get_transaction_history_rejects_bad_uuid() -> None:
    with pytest.raises(ToolExecutionError, match="Invalid transaction ID"):
        await execute_tool(
            "get_transaction_history", {"transaction_id": "nope"}, ALICE, PERSONS
        )


def _category_groups_result() -> object:
    from src.application.use_cases.list_category_groups import (
        CategoryGroupWithCategories,
        ListCategoryGroupsResult,
    )
    from tests.fixtures.factories import make_category, make_category_group

    food = make_category_group(name="Food & Dining")
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
            )
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
        result = await execute_tool(
            "get_budgets", {"year": 2026, "month": 3}, ALICE, PERSONS
        )

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
            ALICE,
            PERSONS,
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
        result = await execute_tool("get_category_setup", {}, ALICE, PERSONS)

    group = result["groups"][0]
    assert group["group"] == "Food & Dining"
    assert "<user_data>Groceries</user_data>" in group["categories"]
    assert result["include_personal_categories"] == ["<user_data>Groceries</user_data>"]
    assert result["unmapped_categories"] == ["<user_data>Mystery</user_data>"]


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
        result = await execute_tool("get_upload_history", {"limit": 2}, ALICE, PERSONS)

    assert result["total_count"] == 3
    assert result["showing"] == 2
    uploads = result["uploads"]
    assert uploads[0]["filename"] == "<user_data>march-5.csv</user_data>"
    assert uploads[1]["filename"] == "<user_data>march-3.csv</user_data>"
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
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=recon,
    ):
        result = await execute_tool(
            "get_reconciliation_report", {"year": 2026, "month": 3}, ALICE, PERSONS
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
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=recon,
    ):
        result = await execute_tool(
            "get_reconciliation_report",
            {"year": 2026, "month": 3, "response_format": "detailed"},
            ALICE,
            PERSONS,
        )

    assert result["group_breakdown"][0]["group"] == "Food & Dining"
    largest = result["largest_transactions"]
    assert len(largest) == 20
    # Sorted by |amount| descending — Store 24 (-34) first.
    assert largest[0]["merchant"] == "<user_data>Store 24</user_data>"
    assert result["unmapped_categories"] == ["<user_data>Mystery</user_data>"]


def _ledger_settlement_record() -> object:
    from src.application.use_cases._shared.settlement_math import (
        LedgerSettlementRecord,
    )
    from src.application.use_cases._shared.settlement_records import SettlementRecord
    from src.domain.ledger import PaymentCoverage
    from tests.fixtures.factories import make_settlement

    linked_tx = uuid.uuid4()
    settlement = make_settlement(
        from_person_id=ALICE.id,
        to_person_id=BOB.id,
        amount=Decimal("147.50"),
        notes="rent catch-up",
        year=2026,
        month=3,
    )
    return LedgerSettlementRecord(
        record=SettlementRecord(
            settlement=settlement,
            linked_transaction_ids=[linked_tx],
        ),
        coverage=PaymentCoverage(
            settlement_id=settlement.id,
            covered=((2026, 3, Decimal("147.50")),),
            unapplied=Decimal(0),
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

    settle = evolve(_settle_result(), all_settlements=[_ledger_settlement_record()])
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
            "get_settlement_activity", {"year": 2026, "month": 3}, ALICE, PERSONS
        )

    assert mock_execute.call_count == 3
    payment = result["settlements"][0]
    assert payment["from"] == "Alice"
    assert payment["notes"] == "<user_data>rent catch-up</user_data>"
    assert payment["recorded_against"] == "2026-03"
    assert payment["covered_months"] == [
        {"month": "2026-03", "amount": pytest.approx(147.5)}
    ]
    assert len(payment["linked_transaction_ids"]) == 1
    cand = result["candidate_transactions"][0]
    assert cand["merchant"] == "<user_data>Venmo Payment</user_data>"
    assert cand["score"] == 5
    assert result["settlement_merchants"] == [
        {
            "name": "<user_data>Venmo</user_data>",
            "pattern": "<user_data>venmo</user_data>",
        }
    ]


@pytest.mark.asyncio
async def test_get_settlement_activity_settled_skips_candidates() -> None:
    from attrs import evolve

    from src.application.use_cases.list_settlement_merchants import (
        ListSettlementMerchantsResult,
    )

    settle = evolve(
        _settle_result(),
        outstanding=None,
        outstanding_span=None,
    )
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        side_effect=[settle, ListSettlementMerchantsResult(merchants=[])],
    ) as mock_execute:
        result = await execute_tool(
            "get_settlement_activity", {"year": 2026, "month": 3}, ALICE, PERSONS
        )

    assert mock_execute.call_count == 2
    assert result["outstanding"] is None
    assert result["candidate_transactions"] == []


def _dashboard_result(**overrides: object) -> object:
    from src.application.use_cases.get_dashboard import (
        GetDashboardResult,
        MonthHistoryEntry,
    )

    defaults: dict[str, object] = {
        "scope": "household",
        "current_person_id": None,
        "current_month": _recon_summary(),
        "upload_statuses": [],
        "household_spending_month": Decimal("1150.00"),
        "household_spending_ytd": Decimal("3400.00"),
        "ytd_settlement": None,
        "ytd_net_settlement": None,
        "ytd_total_settled": Decimal("500.00"),
        "outstanding_balance": SettlementResult(
            amount=Decimal("147.50"),
            from_person_id=ALICE.id,
            to_person_id=BOB.id,
        ),
        "outstanding_span": ((2026, 2), (2026, 3)),
        "month_history": [
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
        "persons": PERSONS,
        "unmapped_categories": ["Mystery"],
        "is_finalized": False,
        "finalized_at": None,
    }
    defaults.update(overrides)
    return GetDashboardResult(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_dashboard_summary_household() -> None:
    with patch(
        "src.application.chat.tool_executor.execute_use_case",
        new_callable=AsyncMock,
        return_value=_dashboard_result(),
    ):
        result = await execute_tool(
            "get_dashboard_summary", {"year": 2026}, ALICE, PERSONS
        )

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
            ALICE,
            PERSONS,
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
            "get_adjustments_preview", {"year": 2026, "month": 3}, ALICE, PERSONS
        )

    command = mock_execute.call_args.args[0]
    assert command.person_id == ALICE.id
    assert result["person"] == "Alice"
    assert result["total_count"] == 1
    row = result["adjustments"][0]
    assert row["merchant"] == "<user_data>Whole Foods</user_data>"
    assert row["account"] == "<user_data>Adjustments</user_data>"
    assert row["amount"] == pytest.approx(-41.71)
