"""Chat tool handlers — each dispatches to existing use cases.

Each tool call runs its own execute_use_case() with a fresh UoW,
matching the existing pattern where use cases own their transaction
boundaries. Results are projected into concise summary dicts — not
raw entity dumps.

Mutation tools (update_budget, update_transaction_split,
bulk_update_transactions) store a pending action and return a
confirmation prompt — they never execute directly. Execution happens
via the confirmation path in the route handler.

Dispatch lives in registry.py — handlers here are wired to tool names
via ToolSpec entries, never called by name from this module.
"""

import calendar
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from src.application.chat.pending_actions import pending_action_store
from src.application.chat.protocols import ToolContext
from src.application.runner import execute_use_case
from src.application.use_cases._shared.finalization import load_period_status
from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.application.use_cases._shared.settlement_math import load_ledger
from src.application.use_cases.export_adjustments import (
    ExportAdjustmentsCommand,
    PreviewAdjustmentsResult,
    PreviewAdjustmentsUseCase,
)
from src.application.use_cases.find_settlement_candidates import (
    FindSettlementCandidatesCommand,
    FindSettlementCandidatesResult,
    FindSettlementCandidatesUseCase,
)
from src.application.use_cases.get_budget_overview import (
    GetBudgetOverviewCommand,
    GetBudgetOverviewResult,
    GetBudgetOverviewUseCase,
)
from src.application.use_cases.get_dashboard import (
    GetDashboardCommand,
    GetDashboardResult,
    GetDashboardUseCase,
)
from src.application.use_cases.get_reconciliation import (
    GetReconciliationCommand,
    GetReconciliationResult,
    GetReconciliationUseCase,
)
from src.application.use_cases.get_settle_up_data import (
    GetSettleUpDataCommand,
    GetSettleUpDataResult,
    GetSettleUpDataUseCase,
)
from src.application.use_cases.get_spending_trends import (
    GetSpendingTrendsCommand,
    GetSpendingTrendsResult,
    GetSpendingTrendsUseCase,
)
from src.application.use_cases.get_tags import GetTagsResult, GetTagsUseCase
from src.application.use_cases.get_transaction_edits import (
    GetTransactionEditsCommand,
    GetTransactionEditsResult,
    GetTransactionEditsUseCase,
)
from src.application.use_cases.get_upload_history import (
    GetUploadHistoryCommand,
    GetUploadHistoryResult,
    GetUploadHistoryUseCase,
)
from src.application.use_cases.list_budgets import ListBudgetsResult, list_budgets
from src.application.use_cases.list_category_groups import (
    ListCategoryGroupsCommand,
    ListCategoryGroupsResult,
    ListCategoryGroupsUseCase,
)
from src.application.use_cases.list_settlement_merchants import (
    ListSettlementMerchantsCommand,
    ListSettlementMerchantsResult,
    ListSettlementMerchantsUseCase,
)
from src.application.use_cases.list_unmapped_categories import (
    ListUnmappedCategoriesCommand,
    ListUnmappedCategoriesResult,
    ListUnmappedCategoriesUseCase,
)
from src.application.use_cases.search_transactions import (
    SearchTransactionsCommand,
    SearchTransactionsResult,
    SearchTransactionsUseCase,
)
from src.domain.entities.person import Person
from src.domain.exceptions import ToolExecutionError
from src.domain.ledger import MonthKey, SettlementLedger
from src.domain.reconciliation import SettlementResult
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


def _person_name(person_id: UUID, persons: list[Person]) -> str:
    for p in persons:
        if p.id == person_id:
            return p.name
    return "Unknown"


_MAX_PAYER_PERCENTAGE = 100
_MAX_BULK_TRANSACTIONS = 100
_MAX_LIST_ROWS = 20
_DEFAULT_UPLOAD_HISTORY = 12
# Mirrors the SettlementMerchant entity's minimum pattern length.
_MIN_MERCHANT_PATTERN = 2


def _fmt(amount: Decimal) -> float:
    return float(round(amount, 2))


def _user_str(value: str) -> str:
    """Label a user-originated string as untrusted data for the model.

    Applies to free-text values imported from CSVs or typed by the couple —
    merchant names, notes, tags, category names, upload filenames, settlement
    notes. Category *group* names stay unwrapped: they are app-managed config
    the system prompt already lists verbatim and tools match exactly.
    The frontend strips the tags before rendering (stripUserData).
    """
    return f"<user_data>{value}</user_data>"


# --- Tool handlers ---


def _owed_dict(
    owed: SettlementResult | None, persons: list[Person]
) -> dict[str, object] | None:
    if owed is None:
        return None
    return {
        "amount": _fmt(owed.amount),
        "from": _person_name(owed.from_person_id, persons),
        "to": _person_name(owed.to_person_id, persons),
    }


def _span_dict(
    span: tuple[MonthKey, MonthKey] | None,
) -> dict[str, str] | None:
    if span is None:
        return None
    return {
        "start": f"{span[0][0]}-{span[0][1]:02d}",
        "end": f"{span[1][0]}-{span[1][1]:02d}",
    }


async def handle_settlement_balance(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    year = cast(int | None, tool_input.get("year"))
    month = cast(int | None, tool_input.get("month"))
    if year is None or month is None:
        return await _outstanding_balance_summary(ctx.persons)
    return await _month_settlement_summary(year, month, ctx.persons)


async def _outstanding_balance_summary(persons: list[Person]) -> dict[str, object]:
    """The couple's total outstanding balance across all months."""

    async def _load(uow: UnitOfWorkProtocol) -> SettlementLedger:
        async with uow:
            ctx = await load_reconciliation_context(uow)
            ledger = (await load_ledger(uow, ctx)).ledger
            return ledger

    ledger = await execute_use_case(_load)
    span = _span_dict(ledger.span)
    summary: dict[str, object] = {
        "scope": "all_months",
        "outstanding": _owed_dict(ledger.outstanding, persons),
        "outstanding_span": span,
        "remaining_balance": _fmt(
            ledger.outstanding.amount if ledger.outstanding else Decimal(0)
        ),
    }
    if ledger.outstanding:
        summary["net_from"] = _person_name(ledger.outstanding.from_person_id, persons)
        summary["net_to"] = _person_name(ledger.outstanding.to_person_id, persons)
        if span:
            summary["month"] = f"{span['start']} to {span['end']}"
    else:
        summary["status"] = "Nothing outstanding — all months are settled"
    return summary


async def _month_settlement_summary(
    year: int, month: int, persons: list[Person]
) -> dict[str, object]:
    command = GetSettleUpDataCommand(year=year, month=month)
    result: GetSettleUpDataResult = await execute_use_case(
        lambda uow: GetSettleUpDataUseCase().execute(command, uow)
    )

    summary: dict[str, object] = {
        "month": f"{result.year}-{result.month:02d}",
        "is_finalized": result.is_finalized,
        "remaining_balance": _fmt(result.remaining_balance),
    }
    if result.owed:
        summary["from"] = _person_name(result.owed.from_person_id, persons)
        summary["to"] = _person_name(result.owed.to_person_id, persons)
        summary["gross_amount"] = _fmt(result.owed.amount)
    else:
        summary["gross_amount"] = 0.0
        summary["status"] = "No settlement needed this month"
    # What remains against this month on the ledger, in its gross direction.
    if result.net_position:
        summary["net_from"] = _person_name(result.net_position.from_person_id, persons)
        summary["net_to"] = _person_name(result.net_position.to_person_id, persons)

    row = next(
        (m for m in result.ledger_months if (m.year, m.month) == (year, month)),
        None,
    )
    if row is not None:
        summary["month_ledger"] = {
            "gross": _fmt(row.gross.amount) if row.gross else 0.0,
            "applied": _fmt(row.applied),
            "remaining": _fmt(row.remaining),
            "status": str(row.status),
        }
    summary["outstanding"] = _owed_dict(result.outstanding, persons)
    summary["outstanding_span"] = _span_dict(result.outstanding_span)

    summary["uploads"] = [
        {"person": us.person_name, "uploaded": us.has_uploaded}
        for us in result.upload_statuses
    ]
    return summary


async def handle_budget_overview(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    scope = cast(Literal["household", "personal"], tool_input.get("scope", "household"))
    command = GetBudgetOverviewCommand(
        year=cast(int, tool_input["year"]),
        month=cast(int, tool_input["month"]),
        scope=scope,
        person_id=ctx.current_user.id if scope == "personal" else None,
    )
    result: GetBudgetOverviewResult = await execute_use_case(
        lambda uow: GetBudgetOverviewUseCase().execute(command, uow)
    )

    overview = result.overview
    groups: list[dict[str, object]] = []
    over_budget: list[str] = []
    for gs in overview.group_statuses:
        entry: dict[str, object] = {
            "name": gs.group_name,
            "spent": _fmt(gs.monthly_spent),
            "budget": _fmt(gs.monthly_budget)
            if gs.monthly_budget is not None
            else None,
            "health": gs.monthly_health,
        }
        groups.append(entry)
        if gs.monthly_health == "over_budget":
            over_budget.append(gs.group_name)

    return {
        "month": f"{overview.year}-{overview.month:02d}",
        "scope": scope,
        "groups": groups,
        "total_spent": _fmt(overview.total_monthly_spent),
        "total_budget": _fmt(overview.total_monthly_budget),
        "over_budget": over_budget,
    }


async def handle_search_transactions(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    group_id: UUID | None = None
    group_name = cast(str | None, tool_input.get("category_group"))
    if group_name:
        group_id = await _resolve_category_group_id(group_name)

    scope = cast(
        Literal["all", "household", "personal"], tool_input.get("scope", "all")
    )
    command = SearchTransactionsCommand(
        year=cast(int, tool_input["year"]),
        month=cast(int, tool_input["month"]),
        merchant=cast(str | None, tool_input.get("merchant")),
        category_group_id=group_id,
        tag=cast(str | None, tool_input.get("tag")),
        scope=scope,
        person_id=ctx.current_user.id if scope == "personal" else None,
    )
    result: SearchTransactionsResult = await execute_use_case(
        lambda uow: SearchTransactionsUseCase().execute(command, uow)
    )

    txns: list[dict[str, object]] = []
    for t in result.transactions:
        split = f"{t.payer_percentage}/{100 - t.payer_percentage}"
        txns.append({
            "id": str(t.id),
            "date": t.date.isoformat(),
            "merchant": _user_str(t.merchant),
            "amount": _fmt(t.amount),
            "category": _user_str(t.category),
            "payer": _person_name(t.payer_person_id, ctx.persons),
            "split": split,
            "household": t.household,
        })
    return {
        "scope": scope,
        "total_count": result.total_count,
        "showing": len(txns),
        "transactions": txns,
    }


async def _load_category_groups() -> ListCategoryGroupsResult:
    return await execute_use_case(
        lambda uow: ListCategoryGroupsUseCase().execute(
            ListCategoryGroupsCommand(), uow
        )
    )


async def _resolve_category_group_id(name: str) -> UUID | None:
    result = await _load_category_groups()
    name_lower = name.lower()
    for item in result.items:
        if item.group.name.lower() == name_lower:
            return item.group.id
    return None


async def handle_spending_by_group(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    result = await handle_budget_overview(tool_input, ctx)
    groups_list = cast(list[dict[str, object]], result["groups"])
    groups: list[dict[str, object]] = [
        {"name": g["name"], "spent": g["spent"]} for g in groups_list
    ]
    return {
        "month": result["month"],
        "groups": groups,
        "total": result["total_spent"],
    }


async def handle_spending_trends(
    tool_input: dict[str, object],
    _ctx: ToolContext,
) -> dict[str, object]:
    command = GetSpendingTrendsCommand(
        year=cast(int, tool_input["year"]),
        comparison_year=cast(int | None, tool_input.get("comparison_year")),
    )
    result: GetSpendingTrendsResult = await execute_use_case(
        lambda uow: GetSpendingTrendsUseCase().execute(command, uow)
    )

    groups: dict[str, list[dict[str, object]]] = {}
    for mg in result.trends.monthly_group_spending:
        groups.setdefault(mg.group_name, []).append({
            "month": f"{result.year}-{mg.month:02d}",
            "amount": _fmt(mg.amount),
        })

    return {
        "year": result.year,
        "groups": [{"name": name, "months": months} for name, months in groups.items()],
    }


async def handle_dashboard_status(
    tool_input: dict[str, object],
    _ctx: ToolContext,
) -> dict[str, object]:
    command = GetSettleUpDataCommand(
        year=cast(int, tool_input["year"]),
        month=cast(int, tool_input["month"]),
    )
    result: GetSettleUpDataResult = await execute_use_case(
        lambda uow: GetSettleUpDataUseCase().execute(command, uow)
    )

    return {
        "month": f"{result.year}-{result.month:02d}",
        "uploads": [
            {
                "person": us.person_name,
                "uploaded": us.has_uploaded,
                "count": us.upload_count,
            }
            for us in result.upload_statuses
        ],
        "is_finalized": result.is_finalized,
        "transaction_count": result.transaction_count,
        "finalization_warnings": result.finalization_warnings,
    }


async def handle_get_tags(
    _tool_input: dict[str, object],
    _ctx: ToolContext,
) -> dict[str, object]:
    result: GetTagsResult = await execute_use_case(
        lambda uow: GetTagsUseCase().execute(uow)
    )
    shown = result.tags[:_MAX_LIST_ROWS]
    return {
        "total_count": len(result.tags),
        "showing": len(shown),
        "tags": [_user_str(t) for t in shown],
    }


async def handle_get_transaction_history(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    try:
        transaction_id = UUID(cast(str, tool_input["transaction_id"]))
    except ValueError as e:
        raise ToolExecutionError(
            f"Invalid transaction ID: {tool_input['transaction_id']}"
        ) from e

    command = GetTransactionEditsCommand(transaction_id=transaction_id)
    result: GetTransactionEditsResult = await execute_use_case(
        lambda uow: GetTransactionEditsUseCase().execute(command, uow)
    )

    shown = result.edits[:_MAX_LIST_ROWS]
    edits: list[dict[str, object]] = [
        {
            "field": e.field_name,
            "old_value": _user_str(e.old_value),
            "new_value": _user_str(e.new_value),
            "edited_at": e.edited_at.isoformat(),
            "edited_by": (
                _person_name(e.edited_by_person_id, ctx.persons)
                if e.edited_by_person_id
                else None
            ),
        }
        for e in shown
    ]
    imported: dict[str, object] | None = None
    if result.import_event is not None:
        imported = {
            "by": _person_name(result.import_event.person_id, ctx.persons),
            "at": result.import_event.imported_at.isoformat(),
        }
    return {
        "transaction_id": str(transaction_id),
        "total_count": len(result.edits),
        "showing": len(shown),
        "edits": edits,
        "imported": imported,
    }


async def handle_get_budgets(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    year = cast(int, tool_input["year"])
    month = cast(int | None, tool_input.get("month"))
    scope = cast(str, tool_input.get("scope", "all"))

    result: ListBudgetsResult = await execute_use_case(
        lambda uow: list_budgets(uow, ctx.current_user.id)
    )
    groups = await _load_category_groups()
    group_names = {item.group.id: item.group.name for item in groups.items}

    rows: list[dict[str, object]] = []
    for b in sorted(result.budgets, key=lambda b: (b.month, b.person_id is not None)):
        if b.year != year or (month is not None and b.month != month):
            continue
        b_scope = "household" if b.person_id is None else "personal"
        if scope not in {"all", b_scope}:
            continue
        rows.append({
            "group": group_names.get(b.group_id, "Unknown"),
            "amount": _fmt(b.monthly_amount),
            "month": f"{b.year}-{b.month:02d}",
            "scope": b_scope,
        })
    return {
        "year": year,
        "scope": scope,
        "total_count": len(rows),
        "showing": min(len(rows), _MAX_LIST_ROWS),
        "budgets": rows[:_MAX_LIST_ROWS],
    }


async def handle_get_category_setup(
    _tool_input: dict[str, object],
    _ctx: ToolContext,
) -> dict[str, object]:
    groups = await _load_category_groups()
    unmapped: ListUnmappedCategoriesResult = await execute_use_case(
        lambda uow: ListUnmappedCategoriesUseCase().execute(
            ListUnmappedCategoriesCommand(), uow
        )
    )
    return {
        "groups": [
            {
                "group": item.group.name,
                "categories": [_user_str(c.name) for c in item.categories],
            }
            for item in groups.items
        ],
        "include_personal_categories": [
            _user_str(c.name)
            for item in groups.items
            for c in item.categories
            if c.include_personal
        ],
        "unmapped_categories": [_user_str(name) for name in unmapped.categories],
    }


async def handle_get_upload_history(
    tool_input: dict[str, object],
    _ctx: ToolContext,
) -> dict[str, object]:
    limit = max(
        1,
        min(
            cast(int, tool_input.get("limit", _DEFAULT_UPLOAD_HISTORY)), _MAX_LIST_ROWS
        ),
    )
    result: GetUploadHistoryResult = await execute_use_case(
        lambda uow: GetUploadHistoryUseCase().execute(GetUploadHistoryCommand(), uow)
    )
    newest_first = sorted(result.entries, key=lambda e: e.uploaded_at, reverse=True)
    shown = newest_first[:limit]
    return {
        "total_count": len(result.entries),
        "showing": len(shown),
        "uploads": [
            {
                "person": e.person_name,
                "filename": _user_str(e.filename),
                "uploaded_at": e.uploaded_at.isoformat(),
                "covers": (
                    f"{e.date_range_start.isoformat()} to "
                    f"{e.date_range_end.isoformat()}"
                    if e.date_range_start and e.date_range_end
                    else None
                ),
                "transaction_count": e.transaction_count,
                "household_count": e.household_count,
            }
            for e in shown
        ],
    }


async def handle_get_reconciliation_report(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    year = cast(int, tool_input["year"])
    month = cast(int, tool_input["month"])
    response_format = cast(str, tool_input.get("response_format", "concise"))

    command = GetReconciliationCommand.from_month(year, month)
    result: GetReconciliationResult = await execute_use_case(
        lambda uow: GetReconciliationUseCase().execute(command, uow)
    )
    s = result.summary

    summary: dict[str, object] = {
        "month": f"{year}-{month:02d}",
        "total_household_spending": _fmt(s.total_household_spending),
        "total_refunds": _fmt(s.total_household_refunds),
        "net_household_spending": _fmt(s.net_household_spending),
        "transaction_count": s.transaction_count,
        "persons": [
            {
                "name": _person_name(ps.person_id, ctx.persons),
                "paid": _fmt(ps.total_paid),
                "fair_share": _fmt(ps.total_share),
            }
            for ps in s.person_summaries
        ],
        # The month's gross position before payments — the running balance
        # lives in get_settlement_balance.
        "gross_settlement": _owed_dict(s.settlement, ctx.persons),
        "uploads": [
            {"person": us.person_name, "uploaded": us.has_uploaded}
            for us in result.upload_statuses
        ],
    }
    if result.unmapped_categories:
        summary["unmapped_categories"] = [
            _user_str(name) for name in result.unmapped_categories
        ]
    if response_format == "detailed":
        summary["group_breakdown"] = [
            {
                "group": b.group_name,
                "total": _fmt(b.total_amount),
                "transaction_count": b.transaction_count,
            }
            for b in s.category_group_breakdowns
        ]
        largest = sorted(
            result.transactions, key=lambda t: abs(t.amount), reverse=True
        )[:_MAX_LIST_ROWS]
        summary["largest_transactions"] = [
            {
                "id": str(t.id),
                "date": t.date.isoformat(),
                "merchant": _user_str(t.merchant),
                "amount": _fmt(t.amount),
                "category": _user_str(t.category),
                "payer": _person_name(t.payer_person_id, ctx.persons),
                "split": f"{t.payer_percentage}/{100 - t.payer_percentage}",
            }
            for t in largest
        ]
    return summary


async def handle_get_settlement_activity(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    year = cast(int, tool_input["year"])
    month = cast(int, tool_input["month"])

    settle_command = GetSettleUpDataCommand(year=year, month=month)
    data: GetSettleUpDataResult = await execute_use_case(
        lambda uow: GetSettleUpDataUseCase().execute(settle_command, uow)
    )
    merchants: ListSettlementMerchantsResult = await execute_use_case(
        lambda uow: ListSettlementMerchantsUseCase().execute(
            ListSettlementMerchantsCommand(), uow
        )
    )

    # all_settlements is chronological ascending — newest first for chat.
    newest_first = list(reversed(data.all_settlements))
    shown = newest_first[:_MAX_LIST_ROWS]
    settlements: list[dict[str, object]] = []
    for lr in shown:
        s = lr.record.settlement
        settlements.append({
            "id": str(s.id),
            "amount": _fmt(s.amount),
            "from": _person_name(s.from_person_id, ctx.persons),
            "to": _person_name(s.to_person_id, ctx.persons),
            "settled_at": s.settled_at.date().isoformat(),
            "method": _user_str(s.method) if s.method else None,
            "notes": _user_str(s.notes) if s.notes else None,
            "is_waived": s.is_waived,
            # Display-only annotation — coverage below is the math.
            "recorded_against": f"{s.year}-{s.month:02d}" if s.year else None,
            "covered_months": [
                {"month": f"{y}-{m:02d}", "amount": _fmt(amount)}
                for (y, m, amount) in lr.coverage.covered
            ],
            "linked_transaction_ids": [
                str(tid) for tid in lr.record.linked_transaction_ids
            ],
        })

    # Candidate transactions only make sense against an amount to settle —
    # match the UI, which searches for the outstanding balance.
    candidates: list[dict[str, object]] = []
    if data.outstanding is not None:
        cand_command = FindSettlementCandidatesCommand(amount=data.outstanding.amount)
        cand: FindSettlementCandidatesResult = await execute_use_case(
            lambda uow: FindSettlementCandidatesUseCase().execute(cand_command, uow)
        )
        candidates = [
            {
                "transaction_id": str(c.transaction.id),
                "date": c.transaction.date.isoformat(),
                "merchant": _user_str(c.transaction.merchant),
                "amount": _fmt(c.transaction.amount),
                "score": c.score,
                "match_reasons": list(c.match_reasons),
            }
            for c in cand.candidates[:_MAX_LIST_ROWS]
        ]

    return {
        "month": f"{year}-{month:02d}",
        "outstanding": _owed_dict(data.outstanding, ctx.persons),
        "outstanding_span": _span_dict(data.outstanding_span),
        "settlements_total": len(data.all_settlements),
        "settlements_showing": len(shown),
        "settlements": settlements,
        "candidate_transactions": candidates,
        "settlement_merchants": [
            {"name": _user_str(m.name), "pattern": _user_str(m.merchant_pattern)}
            for m in merchants.merchants
        ],
    }


async def handle_get_dashboard_summary(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    year = cast(int, tool_input["year"])
    month = cast(int | None, tool_input.get("month"))
    scope = cast(Literal["household", "personal"], tool_input.get("scope", "household"))

    command = GetDashboardCommand(
        year=year,
        month=month,
        scope=scope,
        person_id=ctx.current_user.id if scope == "personal" else None,
    )
    result: GetDashboardResult = await execute_use_case(
        lambda uow: GetDashboardUseCase().execute(command, uow)
    )

    summary: dict[str, object] = {
        "year": year,
        "scope": scope,
        "household_spending_month": _fmt(result.household_spending_month),
        "household_spending_ytd": _fmt(result.household_spending_ytd),
        "ytd_total_settled": _fmt(result.ytd_total_settled),
        "outstanding": _owed_dict(result.outstanding_balance, ctx.persons),
        "outstanding_span": _span_dict(result.outstanding_span),
        "unmapped_category_count": len(result.unmapped_categories),
        "month_history": [
            {
                "month": f"{e.year}-{e.month:02d}",
                "household_spending": _fmt(e.total_household_spending),
                "settlement_gross": _fmt(e.settlement_amount),
                "settlement_remaining": _fmt(e.settlement_remaining),
                "settlement_status": e.settlement_status,
                "finalized": e.is_finalized,
            }
            for e in result.month_history
        ],
    }
    if scope == "personal":
        for key, value in {
            "my_spending_month": result.my_spending_month,
            "my_household_share_month": result.my_household_share_month,
            "my_personal_spending_month": result.my_personal_spending_month,
            "my_spending_ytd": result.my_spending_ytd,
        }.items():
            if value is not None:
                summary[key] = _fmt(value)
    return summary


async def handle_get_adjustments_preview(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    year = cast(int, tool_input["year"])
    month = cast(int, tool_input["month"])

    command = ExportAdjustmentsCommand(
        person_id=ctx.current_user.id, year=year, month=month
    )
    result: PreviewAdjustmentsResult = await execute_use_case(
        lambda uow: PreviewAdjustmentsUseCase().execute(command, uow)
    )
    shown = result.adjustments[:_MAX_LIST_ROWS]
    return {
        "month": f"{year}-{month:02d}",
        "person": result.person_name,
        "total_count": result.adjustment_count,
        "showing": len(shown),
        "adjustments": [
            {
                "date": a.date.isoformat(),
                "merchant": _user_str(a.merchant),
                "category": _user_str(a.category),
                "amount": _fmt(a.amount),
                "account": _user_str(a.account),
            }
            for a in shown
        ],
    }


# --- Mutation handlers (two-phase: propose only, never execute) ---


def _month_label(year: int, month: int) -> str:
    return f"{calendar.month_name[month]} {year}"


async def _check_finalization(year: int, month: int) -> None:
    """Raise ToolExecutionError if the period is finalized."""

    async def _query(uow: UnitOfWorkProtocol) -> tuple[bool, object]:
        async with uow:
            return await load_period_status(uow, year, month)

    is_finalized, _ = await execute_use_case(_query)
    if is_finalized:
        raise ToolExecutionError(
            f"{_month_label(year, month)} is finalized. "
            "The user needs to unfinalize it before making changes."
        )


async def _check_category_exists(category: str) -> None:
    """Raise ToolExecutionError if the category doesn't exist.

    Mirrors the confirm-time check in `confirmed_actions._exec_bulk` so a
    typo'd category is rejected at propose time — before the confirmation
    card is even shown — rather than only at confirm time.
    """

    async def _query(uow: UnitOfWorkProtocol) -> bool:
        async with uow:
            existing = await uow.categories.get_by_name(category)
            return existing is not None

    exists = await execute_use_case(_query)
    if not exists:
        raise ToolExecutionError(f"Unknown category: {category}")


def _propose_action(
    current_user: Person,
    tool_name: str,
    tool_input: dict[str, object],
    description: str,
    details: dict[str, object],
) -> dict[str, object]:
    """Store a pending action and return a pending_confirmation response."""
    action = pending_action_store.create(
        person_id=current_user.id,
        tool_name=tool_name,
        tool_input=dict(tool_input),
        description=description,
        details=details,
    )
    return {
        "status": "pending_confirmation",
        "action_id": str(action.action_id),
        "description": description,
        "details": details,
    }


async def handle_update_budget(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    group_name = cast(str, tool_input["group_name"])
    amount = cast(int | float, tool_input["amount"])
    year = cast(int, tool_input["year"])
    month = cast(int, tool_input["month"])
    scope = cast(str, tool_input.get("scope", "household"))

    await _check_finalization(year, month)

    group_id = await _resolve_category_group_id(group_name)
    if group_id is None:
        raise ToolExecutionError(f"Unknown category group: {group_name}")

    person_id = ctx.current_user.id if scope == "personal" else None
    description = (
        f"Set {group_name} budget to ${amount:,.2f} "
        f"for {_month_label(year, month)} ({scope})"
    )
    details: dict[str, object] = {
        "group_name": group_name,
        "group_id": str(group_id),
        "amount": amount,
        "year": year,
        "month": month,
        "scope": scope,
        "person_id": str(person_id) if person_id else None,
    }
    return _propose_action(
        ctx.current_user, "update_budget", tool_input, description, details
    )


def _parse_split_entries(
    tool_input: dict[str, object],
) -> list[tuple[UUID, int]]:
    """Accept the batch `splits` form or the legacy single-entry form."""
    raw_entries: list[dict[str, object]]
    if tool_input.get("splits"):
        raw_entries = cast(list[dict[str, object]], tool_input["splits"])
    elif "transaction_id" in tool_input and "payer_percentage" in tool_input:
        raw_entries = [
            {
                "transaction_id": tool_input["transaction_id"],
                "payer_percentage": tool_input["payer_percentage"],
            }
        ]
    else:
        raise ToolExecutionError(
            "Provide either transaction_id + payer_percentage, or a splits array"
        )
    if len(raw_entries) > _MAX_BULK_TRANSACTIONS:
        raise ToolExecutionError(
            f"Maximum {_MAX_BULK_TRANSACTIONS} splits per call, got {len(raw_entries)}"
        )

    entries: list[tuple[UUID, int]] = []
    for raw in raw_entries:
        try:
            transaction_id = UUID(cast(str, raw["transaction_id"]))
        except (KeyError, ValueError, TypeError) as e:
            raise ToolExecutionError(
                f"Invalid transaction ID: {raw.get('transaction_id')}"
            ) from e
        payer_percentage = cast(int, raw["payer_percentage"])
        if not 0 <= payer_percentage <= _MAX_PAYER_PERCENTAGE:
            raise ToolExecutionError(
                f"payer_percentage must be 0-100, got {payer_percentage}"
            )
        entries.append((transaction_id, payer_percentage))
    return entries


async def handle_update_transaction_split(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    entries = _parse_split_entries(tool_input)

    # Fetch all transactions + check finalization in a single UoW.
    async def _fetch(uow: UnitOfWorkProtocol) -> list[dict[str, object]]:
        async with uow:
            rows: list[dict[str, object]] = []
            checked_months: set[tuple[int, int]] = set()
            for transaction_id, payer_percentage in entries:
                tx = await uow.transactions.get_by_id(transaction_id)
                if tx is None:
                    raise ToolExecutionError(f"Transaction {transaction_id} not found")
                month_key = (tx.date.year, tx.date.month)
                if month_key not in checked_months:
                    is_finalized, _ = await load_period_status(uow, *month_key)
                    if is_finalized:
                        raise ToolExecutionError(
                            f"{_month_label(*month_key)} is finalized. The user "
                            "needs to unfinalize it before making changes."
                        )
                    checked_months.add(month_key)
                rows.append({
                    "transaction_id": str(tx.id),
                    "merchant": _user_str(tx.merchant),
                    "date": tx.date.isoformat(),
                    "amount": _fmt(tx.amount),
                    "payer": _person_name(tx.payer_person_id, ctx.persons),
                    "current_split": (
                        f"{tx.payer_percentage}/{100 - tx.payer_percentage}"
                    ),
                    "new_split": f"{payer_percentage}/{100 - payer_percentage}",
                    "payer_percentage": payer_percentage,
                })
            return rows

    rows = await execute_use_case(_fetch)

    if len(rows) == 1:
        row = rows[0]
        description = (
            f"Change {row['merchant']} ({row['date']}) "
            f"split from {row['current_split']} to {row['new_split']}"
        )
    else:
        new_splits = {cast(str, r["new_split"]) for r in rows}
        suffix = f" to {next(iter(new_splits))}" if len(new_splits) == 1 else ""
        description = f"Change splits on {len(rows)} transactions{suffix}"

    # Single-entry proposals keep the flat keys the frontend SplitDetails
    # card renders; the executor always reads the splits list.
    details: dict[str, object] = {"splits": rows, "count": len(rows)}
    if len(rows) == 1:
        details.update(rows[0])
    return _propose_action(
        ctx.current_user, "update_transaction_split", tool_input, description, details
    )


async def handle_bulk_update_transactions(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    raw_ids = cast(list[str], tool_input["transaction_ids"])
    if len(raw_ids) > _MAX_BULK_TRANSACTIONS:
        raise ToolExecutionError(
            f"Maximum 100 transactions per bulk update, got {len(raw_ids)}"
        )

    try:
        transaction_ids = [UUID(tid) for tid in raw_ids]
    except ValueError as e:
        raise ToolExecutionError(f"Invalid transaction ID: {e}") from e

    # Validate first transaction exists + check finalization in one UoW
    async def _validate(uow: UnitOfWorkProtocol) -> None:
        async with uow:
            first = await uow.transactions.get_by_id(transaction_ids[0])
            if first is None:
                raise ToolExecutionError(f"Transaction {transaction_ids[0]} not found")
            is_finalized, _ = await load_period_status(
                uow, first.date.year, first.date.month
            )
            if is_finalized:
                raise ToolExecutionError(
                    f"{_month_label(first.date.year, first.date.month)} is finalized. "
                    "The user needs to unfinalize it before making changes."
                )

    await execute_use_case(_validate)

    changes = cast(dict[str, object], tool_input.get("changes", {}))
    if not changes:
        raise ToolExecutionError("No changes specified")

    if "category" in changes:
        await _check_category_exists(cast(str, changes["category"]))

    parts: list[str] = []
    if "household" in changes:
        parts.append(f"household={'true' if changes['household'] else 'false'}")
    if "payer_percentage" in changes:
        pct = cast(int, changes["payer_percentage"])
        parts.append(f"split to {pct}/{100 - pct}")
    if "is_excluded" in changes:
        parts.append("exclude" if changes["is_excluded"] else "include")
    if "category" in changes:
        parts.append(f"category to {changes['category']}")
    if "tags" in changes:
        tag_info = cast(dict[str, object], changes["tags"])
        tag_action = cast(str, tag_info["action"])
        values = cast(list[str], tag_info["values"])
        parts.append(f"{tag_action} tags: {', '.join(values)}")

    change_desc = ", ".join(parts) if parts else "no changes"
    count = len(transaction_ids)
    description = (
        f"Update {count} transaction{'s' if count != 1 else ''}: {change_desc}"
    )
    details: dict[str, object] = {
        "transaction_ids": [str(tid) for tid in transaction_ids],
        "count": count,
        "changes": changes,
    }
    return _propose_action(
        ctx.current_user, "bulk_update_transactions", tool_input, description, details
    )


def _resolve_person(name: str, persons: list[Person]) -> Person:
    match = next((p for p in persons if p.name.lower() == name.lower()), None)
    if match is None:
        valid = ", ".join(p.name for p in persons)
        raise ToolExecutionError(f"Unknown person: {name}. The couple is: {valid}")
    return match


async def _require_group(name: str) -> tuple[UUID, list[str]]:
    """Resolve a category group name → id, with an actionable error."""
    groups = await _load_category_groups()
    valid_names = [item.group.name for item in groups.items]
    match = next(
        (
            item.group
            for item in groups.items
            if item.group.name.lower() == name.lower()
        ),
        None,
    )
    if match is None:
        raise ToolExecutionError(
            f"Unknown category group: {name}. Valid groups: {', '.join(valid_names)}"
        )
    return match.id, valid_names


async def handle_delete_budget(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    group_name = cast(str, tool_input["group_name"])
    year = cast(int, tool_input["year"])
    month = cast(int, tool_input["month"])
    scope = cast(str, tool_input.get("scope", "household"))

    await _check_finalization(year, month)
    group_id, _ = await _require_group(group_name)

    budgets = await execute_use_case(lambda uow: list_budgets(uow, ctx.current_user.id))
    target_person = ctx.current_user.id if scope == "personal" else None
    budget = next(
        (
            b
            for b in budgets.budgets
            if b.group_id == group_id
            and (b.year, b.month) == (year, month)
            and b.person_id == target_person
        ),
        None,
    )
    if budget is None:
        raise ToolExecutionError(
            f"No {scope} budget for {group_name} in {_month_label(year, month)}"
        )

    description = (
        f"Delete the {group_name} budget of ${_fmt(budget.monthly_amount):,.2f} "
        f"for {_month_label(year, month)} ({scope})"
    )
    details: dict[str, object] = {
        "budget_id": str(budget.id),
        "group_name": group_name,
        "current_amount": _fmt(budget.monthly_amount),
        "year": year,
        "month": month,
        "scope": scope,
    }
    return _propose_action(
        ctx.current_user, "delete_budget", tool_input, description, details
    )


async def handle_copy_budgets(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    from_year = cast(int, tool_input["from_year"])
    from_month = cast(int, tool_input["from_month"])
    to_year = cast(int, tool_input["to_year"])
    to_month = cast(int, tool_input["to_month"])
    if (from_year, from_month) == (to_year, to_month):
        raise ToolExecutionError("Source and target month must differ")

    await _check_finalization(to_year, to_month)

    budgets = (
        await execute_use_case(lambda uow: list_budgets(uow, ctx.current_user.id))
    ).budgets
    source = [b for b in budgets if (b.year, b.month) == (from_year, from_month)]
    if not source:
        raise ToolExecutionError(
            f"No budgets found for {_month_label(from_year, from_month)}"
        )
    target_keys = {
        (b.group_id, b.person_id)
        for b in budgets
        if (b.year, b.month) == (to_year, to_month)
    }
    to_copy = [b for b in source if (b.group_id, b.person_id) not in target_keys]
    skipped = len(source) - len(to_copy)
    if not to_copy:
        raise ToolExecutionError(
            f"All {len(source)} budgets already exist in "
            f"{_month_label(to_year, to_month)} — nothing to copy"
        )

    description = (
        f"Copy {len(to_copy)} budget{'s' if len(to_copy) != 1 else ''} from "
        f"{_month_label(from_year, from_month)} to {_month_label(to_year, to_month)}"
        + (f" ({skipped} already set, skipped)" if skipped else "")
    )
    details: dict[str, object] = {
        "from": f"{from_year}-{from_month:02d}",
        "to": f"{to_year}-{to_month:02d}",
        "copy_count": len(to_copy),
        "skipped_count": skipped,
        "total_amount": _fmt(Decimal(sum(b.monthly_amount for b in to_copy))),
        "from_year": from_year,
        "from_month": from_month,
        "to_year": to_year,
        "to_month": to_month,
    }
    return _propose_action(
        ctx.current_user, "copy_budgets", tool_input, description, details
    )


async def handle_manage_category_group(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    action = cast(str, tool_input["action"])
    name = cast(str, tool_input["name"])
    if not name.strip():
        raise ToolExecutionError("Group name must not be empty")

    details: dict[str, object] = {"action": action, "name": name}
    if action == "create":
        if await _resolve_category_group_id(name) is not None:
            raise ToolExecutionError(f"Category group '{name}' already exists")
        description = f"Create category group '{name}'"
    elif action == "rename":
        new_name = cast(str | None, tool_input.get("new_name"))
        if not new_name or not new_name.strip():
            raise ToolExecutionError("new_name is required for rename")
        group_id, _ = await _require_group(name)
        if await _resolve_category_group_id(new_name) is not None:
            raise ToolExecutionError(f"Category group '{new_name}' already exists")
        description = f"Rename category group '{name}' to '{new_name}'"
        details.update({"group_id": str(group_id), "new_name": new_name})
    elif action == "delete":
        group_id, _ = await _require_group(name)
        groups = await _load_category_groups()
        category_count = next(
            len(item.categories) for item in groups.items if item.group.id == group_id
        )
        move_to_name = cast(str | None, tool_input.get("move_categories_to"))
        move_to_id: UUID | None = None
        if move_to_name:
            move_to_id, _ = await _require_group(move_to_name)
            if move_to_id == group_id:
                raise ToolExecutionError(
                    "Cannot move categories to the group being deleted"
                )
            fate = f"move to {move_to_name}"
        else:
            fate = "become unmapped"
        description = (
            f"Delete category group '{name}' — its {category_count} "
            f"categor{'ies' if category_count != 1 else 'y'} {fate}; "
            "its budgets are deleted"
        )
        details.update({
            "group_id": str(group_id),
            "category_count": category_count,
            "categories_fate": fate,
            "move_categories_to": move_to_name,
            "move_to_group_id": str(move_to_id) if move_to_id else None,
        })
    else:  # pragma: no cover — enum-constrained by the schema
        raise ToolExecutionError(f"Unknown action: {action}")

    return _propose_action(
        ctx.current_user, "manage_category_group", tool_input, description, details
    )


async def handle_map_categories(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    raw_mappings = cast(list[dict[str, object]], tool_input.get("mappings") or [])
    if not raw_mappings:
        raise ToolExecutionError("No mappings specified")
    if len(raw_mappings) > _MAX_BULK_TRANSACTIONS:
        raise ToolExecutionError(f"Maximum {_MAX_BULK_TRANSACTIONS} mappings per call")

    groups = await _load_category_groups()
    by_name_lower = {item.group.name.lower(): item.group for item in groups.items}
    valid_names = [item.group.name for item in groups.items]

    resolved: list[dict[str, object]] = []
    for entry in raw_mappings:
        category = cast(str, entry["category"])
        group_name = cast(str, entry["group_name"])
        group = by_name_lower.get(group_name.lower())
        if group is None:
            raise ToolExecutionError(
                f"Unknown category group: {group_name}. "
                f"Valid groups: {', '.join(valid_names)}"
            )
        resolved.append({
            "category": _user_str(category),
            "group_name": group.name,
            "group_id": str(group.id),
        })

    count = len(resolved)
    description = (
        f"Map {count} categor{'ies' if count != 1 else 'y'} to "
        f"{'their groups' if count != 1 else cast(str, resolved[0]['group_name'])}"
    )
    details: dict[str, object] = {"mappings": resolved, "count": count}
    return _propose_action(
        ctx.current_user, "map_categories", tool_input, description, details
    )


async def handle_set_category_personal(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    category = cast(str, tool_input["category"])
    include_personal = cast(bool, tool_input["include_personal"])

    async def _query(uow: UnitOfWorkProtocol) -> bool:
        async with uow:
            existing = await uow.categories.get_by_name(category)
            if existing is None:
                raise ToolExecutionError(f"Unknown category: {category}")
            return existing.include_personal

    current = await execute_use_case(_query)
    if current == include_personal:
        raise ToolExecutionError(
            f"'{category}' already has include_personal={include_personal}"
        )

    verb = "count" if include_personal else "stop counting"
    description = (
        f"{verb.capitalize()} personal spending in '{category}' "
        "toward its group's budget"
    )
    details: dict[str, object] = {
        "category": _user_str(category),
        "current": current,
        "new": include_personal,
    }
    return _propose_action(
        ctx.current_user, "set_category_personal", tool_input, description, details
    )


async def handle_finalize_period(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    year = cast(int, tool_input["year"])
    month = cast(int, tool_input["month"])
    notes = cast(str, tool_input.get("notes", ""))

    # Reuse the settle-up snapshot: it carries both the current lock state
    # and the advisory warnings the app shows before finalizing.
    command = GetSettleUpDataCommand(year=year, month=month)
    data: GetSettleUpDataResult = await execute_use_case(
        lambda uow: GetSettleUpDataUseCase().execute(command, uow)
    )
    if data.is_finalized:
        raise ToolExecutionError(f"{_month_label(year, month)} is already finalized")

    description = f"Finalize {_month_label(year, month)} (lock the month)"
    details: dict[str, object] = {
        "year": year,
        "month": month,
        "notes": notes,
        # Advisory, not blocking — matching the app's finalize dialog.
        "warnings": data.finalization_warnings,
        "transaction_count": data.transaction_count,
    }
    return _propose_action(
        ctx.current_user, "finalize_period", tool_input, description, details
    )


async def handle_unfinalize_period(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    year = cast(int, tool_input["year"])
    month = cast(int, tool_input["month"])

    async def _query(uow: UnitOfWorkProtocol) -> tuple[bool, object]:
        async with uow:
            return await load_period_status(uow, year, month)

    is_finalized, _ = await execute_use_case(_query)
    if not is_finalized:
        raise ToolExecutionError(f"{_month_label(year, month)} is not finalized")

    description = f"Unlock {_month_label(year, month)} for editing"
    details: dict[str, object] = {"year": year, "month": month}
    return _propose_action(
        ctx.current_user, "unfinalize_period", tool_input, description, details
    )


async def handle_record_settlement(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    from_person = _resolve_person(cast(str, tool_input["from_person"]), ctx.persons)
    to_person = _resolve_person(cast(str, tool_input["to_person"]), ctx.persons)
    if from_person.id == to_person.id:
        raise ToolExecutionError("from_person and to_person must differ")

    amount = Decimal(str(tool_input["amount"]))
    if amount <= 0:
        raise ToolExecutionError(f"amount must be positive, got {amount}")

    year = cast(int | None, tool_input.get("year"))
    month = cast(int | None, tool_input.get("month"))
    if (year is None) != (month is None):
        raise ToolExecutionError("year and month must be set together or not at all")

    raw_linked = cast(list[str], tool_input.get("linked_transaction_ids") or [])
    try:
        linked_uuids = [UUID(tid) for tid in raw_linked]
    except ValueError as e:
        raise ToolExecutionError(f"Invalid transaction ID: {e}") from e
    linked_ids = [str(tid) for tid in linked_uuids]

    if linked_uuids:
        # Propose-time existence check — the executor re-validates links
        # and month locks, but a typo'd ID should fail before the card.
        async def _verify(uow: UnitOfWorkProtocol) -> None:
            async with uow:
                txs = await uow.transactions.get_by_ids(linked_uuids)
                missing = set(linked_uuids) - {tx.id for tx in txs}
                if missing:
                    raise ToolExecutionError(
                        f"Transactions not found: {', '.join(map(str, missing))}"
                    )

        await execute_use_case(_verify)

    method = cast(str, tool_input.get("method", ""))
    notes = cast(str, tool_input.get("notes", ""))

    annotation = (
        f" (recorded against {_month_label(year, month)})"
        if year is not None and month is not None
        else ""
    )
    linked_note = (
        f", linking {len(linked_ids)} transaction{'s' if len(linked_ids) != 1 else ''}"
        if linked_ids
        else ""
    )
    description = (
        f"Record ${amount:,.2f} from {from_person.name} to {to_person.name}"
        + (f" via {method}" if method else "")
        + annotation
        + linked_note
    )
    details: dict[str, object] = {
        "amount": _fmt(amount),
        "from": from_person.name,
        "to": to_person.name,
        "from_person_id": str(from_person.id),
        "to_person_id": str(to_person.id),
        "method": method or None,
        "notes": _user_str(notes) if notes else None,
        "recorded_against": f"{year}-{month:02d}" if year and month else None,
        "year": year,
        "month": month,
        "linked_transaction_ids": linked_ids,
    }
    return _propose_action(
        ctx.current_user, "record_settlement", tool_input, description, details
    )


async def handle_waive_settlement(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    async def _load(uow: UnitOfWorkProtocol) -> SettlementLedger:
        async with uow:
            ctx = await load_reconciliation_context(uow)
            return (await load_ledger(uow, ctx)).ledger

    ledger = await execute_use_case(_load)
    if ledger.outstanding is None:
        raise ToolExecutionError("Balance is already settled — nothing to waive")

    outstanding = ledger.outstanding
    from_name = _person_name(outstanding.from_person_id, ctx.persons)
    to_name = _person_name(outstanding.to_person_id, ctx.persons)
    notes = cast(str, tool_input.get("notes", ""))
    span = _span_dict(ledger.span)

    description = (
        f"Waive the outstanding balance of ${outstanding.amount:,.2f} "
        f"that {from_name} owes {to_name}"
    )
    details: dict[str, object] = {
        "amount": _fmt(outstanding.amount),
        "from": from_name,
        "to": to_name,
        "from_person_id": str(outstanding.from_person_id),
        "to_person_id": str(outstanding.to_person_id),
        "covers": f"{span['start']} to {span['end']}" if span else None,
        "notes": _user_str(notes) if notes else None,
    }
    return _propose_action(
        ctx.current_user, "waive_settlement", tool_input, description, details
    )


async def handle_delete_settlement(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    try:
        settlement_id = UUID(cast(str, tool_input["settlement_id"]))
    except ValueError as e:
        raise ToolExecutionError(
            f"Invalid settlement ID: {tool_input['settlement_id']}"
        ) from e

    async def _fetch(uow: UnitOfWorkProtocol) -> dict[str, object]:
        async with uow:
            settlement = await uow.settlements.get_by_id(settlement_id)
            if settlement is None:
                raise ToolExecutionError(
                    f"Settlement {settlement_id} not found — use "
                    "get_settlement_activity to list recorded settlements"
                )
            links = await uow.settlement_transaction_links.get_by_settlement_ids([
                settlement_id
            ])
            return {
                "amount": _fmt(settlement.amount),
                "from": _person_name(settlement.from_person_id, ctx.persons),
                "to": _person_name(settlement.to_person_id, ctx.persons),
                "settled_at": settlement.settled_at.date().isoformat(),
                "is_waived": settlement.is_waived,
                "linked_transaction_count": len(links),
            }

    info = await execute_use_case(_fetch)

    kind = "waived settlement" if info["is_waived"] else "settlement"
    description = (
        f"Delete the ${cast(float, info['amount']):,.2f} {kind} from "
        f"{info['from']} to {info['to']} recorded {info['settled_at']}"
    )
    details: dict[str, object] = {"settlement_id": str(settlement_id), **info}
    return _propose_action(
        ctx.current_user, "delete_settlement", tool_input, description, details
    )


async def handle_link_settlement_transaction(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    try:
        transaction_id = UUID(cast(str, tool_input["transaction_id"]))
    except ValueError as e:
        raise ToolExecutionError(
            f"Invalid transaction ID: {tool_input['transaction_id']}"
        ) from e
    raw_settlement = cast(str | None, tool_input.get("settlement_id"))
    settlement_id = None
    if raw_settlement:
        try:
            settlement_id = UUID(raw_settlement)
        except ValueError as e:
            raise ToolExecutionError(f"Invalid settlement ID: {raw_settlement}") from e

    async def _fetch(uow: UnitOfWorkProtocol) -> dict[str, object]:
        async with uow:
            tx = await uow.transactions.get_by_id(transaction_id)
            if tx is None:
                raise ToolExecutionError(f"Transaction {transaction_id} not found")
            if tx.is_settlement:
                raise ToolExecutionError(
                    f"{tx.merchant} ({tx.date.isoformat()}) is already marked "
                    "as a settlement transfer"
                )
            is_finalized, _ = await load_period_status(uow, tx.date.year, tx.date.month)
            if is_finalized:
                raise ToolExecutionError(
                    f"{_month_label(tx.date.year, tx.date.month)} is finalized. "
                    "The user needs to unfinalize it before making changes."
                )
            if settlement_id is not None:
                settlement = await uow.settlements.get_by_id(settlement_id)
                if settlement is None:
                    raise ToolExecutionError(f"Settlement {settlement_id} not found")
            return {
                "merchant": _user_str(tx.merchant),
                "date": tx.date.isoformat(),
                "amount": _fmt(tx.amount),
                "payer": _person_name(tx.payer_person_id, ctx.persons),
            }

    info = await execute_use_case(_fetch)

    link_note = " and link it to the recorded settlement" if settlement_id else ""
    description = (
        f"Mark {info['merchant']} ({info['date']}, "
        f"${abs(cast(float, info['amount'])):,.2f}) as a settlement "
        f"transfer{link_note}"
    )
    details: dict[str, object] = {
        "transaction_id": str(transaction_id),
        "settlement_id": str(settlement_id) if settlement_id else None,
        **info,
    }
    return _propose_action(
        ctx.current_user,
        "link_settlement_transaction",
        tool_input,
        description,
        details,
    )


async def handle_unlink_settlement_transaction(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    try:
        settlement_id = UUID(cast(str, tool_input["settlement_id"]))
        transaction_id = UUID(cast(str, tool_input["transaction_id"]))
    except ValueError as e:
        raise ToolExecutionError(f"Invalid ID: {e}") from e

    async def _fetch(uow: UnitOfWorkProtocol) -> dict[str, object]:
        async with uow:
            settlement = await uow.settlements.get_by_id(settlement_id)
            if settlement is None:
                raise ToolExecutionError(f"Settlement {settlement_id} not found")
            tx = await uow.transactions.get_by_id(transaction_id)
            if tx is None:
                raise ToolExecutionError(f"Transaction {transaction_id} not found")
            links = await uow.settlement_transaction_links.get_by_transaction_id(
                transaction_id
            )
            if not any(link.settlement_id == settlement_id for link in links):
                raise ToolExecutionError(
                    f"{tx.merchant} ({tx.date.isoformat()}) is not linked to "
                    "that settlement — get_settlement_activity lists the links"
                )
            is_finalized, _ = await load_period_status(uow, tx.date.year, tx.date.month)
            if is_finalized:
                raise ToolExecutionError(
                    f"{_month_label(tx.date.year, tx.date.month)} is finalized. "
                    "The user needs to unfinalize it before making changes."
                )
            return {
                "merchant": _user_str(tx.merchant),
                "date": tx.date.isoformat(),
                "amount": _fmt(tx.amount),
            }

    info = await execute_use_case(_fetch)

    description = (
        f"Unlink {info['merchant']} ({info['date']}) from the settlement — "
        "it re-enters settlement math"
    )
    details: dict[str, object] = {
        "settlement_id": str(settlement_id),
        "transaction_id": str(transaction_id),
        **info,
    }
    return _propose_action(
        ctx.current_user,
        "unlink_settlement_transaction",
        tool_input,
        description,
        details,
    )


async def handle_manage_settlement_merchant(
    tool_input: dict[str, object],
    ctx: ToolContext,
) -> dict[str, object]:
    action = cast(str, tool_input["action"])
    name = cast(str, tool_input["name"])
    if not name.strip():
        raise ToolExecutionError("Merchant name must not be empty")

    merchants = await execute_use_case(
        lambda uow: ListSettlementMerchantsUseCase().execute(
            ListSettlementMerchantsCommand(), uow
        )
    )
    existing = next(
        (m for m in merchants.merchants if m.name.lower() == name.lower()), None
    )

    details: dict[str, object] = {"action": action, "name": _user_str(name)}
    if action == "add":
        pattern = cast(str | None, tool_input.get("pattern"))
        if not pattern or len(pattern) < _MIN_MERCHANT_PATTERN:
            raise ToolExecutionError("pattern is required for add (min 2 characters)")
        if existing is not None:
            raise ToolExecutionError(
                f"Settlement merchant '{existing.name}' already exists"
            )
        description = (
            f"Add settlement merchant '{name}' matching merchants "
            f"containing '{pattern}'"
        )
        details["pattern"] = _user_str(pattern)
        details["raw_name"] = name
        details["raw_pattern"] = pattern
    elif action == "remove":
        if existing is None:
            valid = ", ".join(m.name for m in merchants.merchants) or "(none)"
            raise ToolExecutionError(
                f"Unknown settlement merchant: {name}. Configured: {valid}"
            )
        description = (
            f"Remove settlement merchant '{existing.name}' "
            f"(pattern '{existing.merchant_pattern}')"
        )
        details["merchant_id"] = str(existing.id)
        details["pattern"] = _user_str(existing.merchant_pattern)
    else:  # pragma: no cover — enum-constrained by the schema
        raise ToolExecutionError(f"Unknown action: {action}")

    return _propose_action(
        ctx.current_user, "manage_settlement_merchant", tool_input, description, details
    )
