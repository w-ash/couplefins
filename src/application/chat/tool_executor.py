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
    _current_user: Person,
    persons: list[Person],
) -> dict[str, object]:
    year = cast(int | None, tool_input.get("year"))
    month = cast(int | None, tool_input.get("month"))
    if year is None or month is None:
        return await _outstanding_balance_summary(persons)
    return await _month_settlement_summary(year, month, persons)


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
    current_user: Person,
    _persons: list[Person],
) -> dict[str, object]:
    scope = cast(Literal["household", "personal"], tool_input.get("scope", "household"))
    command = GetBudgetOverviewCommand(
        year=cast(int, tool_input["year"]),
        month=cast(int, tool_input["month"]),
        scope=scope,
        person_id=current_user.id if scope == "personal" else None,
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
    current_user: Person,
    persons: list[Person],
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
        person_id=current_user.id if scope == "personal" else None,
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
            "payer": _person_name(t.payer_person_id, persons),
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
    current_user: Person,
    persons: list[Person],
) -> dict[str, object]:
    result = await handle_budget_overview(tool_input, current_user, persons)
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
    _current_user: Person,
    _persons: list[Person],
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
    _current_user: Person,
    _persons: list[Person],
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
    _current_user: Person,
    _persons: list[Person],
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
    _current_user: Person,
    persons: list[Person],
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
                _person_name(e.edited_by_person_id, persons)
                if e.edited_by_person_id
                else None
            ),
        }
        for e in shown
    ]
    imported: dict[str, object] | None = None
    if result.import_event is not None:
        imported = {
            "by": _person_name(result.import_event.person_id, persons),
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
    current_user: Person,
    _persons: list[Person],
) -> dict[str, object]:
    year = cast(int, tool_input["year"])
    month = cast(int | None, tool_input.get("month"))
    scope = cast(str, tool_input.get("scope", "all"))

    result: ListBudgetsResult = await execute_use_case(
        lambda uow: list_budgets(uow, current_user.id)
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
    _current_user: Person,
    _persons: list[Person],
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
    _current_user: Person,
    _persons: list[Person],
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
    _current_user: Person,
    persons: list[Person],
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
                "name": _person_name(ps.person_id, persons),
                "paid": _fmt(ps.total_paid),
                "fair_share": _fmt(ps.total_share),
            }
            for ps in s.person_summaries
        ],
        # The month's gross position before payments — the running balance
        # lives in get_settlement_balance.
        "gross_settlement": _owed_dict(s.settlement, persons),
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
                "payer": _person_name(t.payer_person_id, persons),
                "split": f"{t.payer_percentage}/{100 - t.payer_percentage}",
            }
            for t in largest
        ]
    return summary


async def handle_get_settlement_activity(
    tool_input: dict[str, object],
    _current_user: Person,
    persons: list[Person],
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
            "from": _person_name(s.from_person_id, persons),
            "to": _person_name(s.to_person_id, persons),
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
        "outstanding": _owed_dict(data.outstanding, persons),
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
    current_user: Person,
    persons: list[Person],
) -> dict[str, object]:
    year = cast(int, tool_input["year"])
    month = cast(int | None, tool_input.get("month"))
    scope = cast(Literal["household", "personal"], tool_input.get("scope", "household"))

    command = GetDashboardCommand(
        year=year,
        month=month,
        scope=scope,
        person_id=current_user.id if scope == "personal" else None,
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
        "outstanding": _owed_dict(result.outstanding_balance, persons),
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
    current_user: Person,
    _persons: list[Person],
) -> dict[str, object]:
    year = cast(int, tool_input["year"])
    month = cast(int, tool_input["month"])

    command = ExportAdjustmentsCommand(
        person_id=current_user.id, year=year, month=month
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
    current_user: Person,
    _persons: list[Person],
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

    person_id = current_user.id if scope == "personal" else None
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
        current_user, "update_budget", tool_input, description, details
    )


async def handle_update_transaction_split(
    tool_input: dict[str, object],
    current_user: Person,
    persons: list[Person],
) -> dict[str, object]:
    try:
        transaction_id = UUID(cast(str, tool_input["transaction_id"]))
    except ValueError as e:
        raise ToolExecutionError(
            f"Invalid transaction ID: {tool_input['transaction_id']}"
        ) from e

    payer_percentage = cast(int, tool_input["payer_percentage"])
    if not 0 <= payer_percentage <= _MAX_PAYER_PERCENTAGE:
        raise ToolExecutionError(
            f"payer_percentage must be 0-100, got {payer_percentage}"
        )

    # Fetch transaction + check finalization in a single UoW
    async def _fetch(uow: UnitOfWorkProtocol) -> dict[str, object]:
        async with uow:
            tx = await uow.transactions.get_by_id(transaction_id)
            if tx is None:
                raise ToolExecutionError(f"Transaction {transaction_id} not found")
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
                "current_split": f"{tx.payer_percentage}/{100 - tx.payer_percentage}",
                "payer": _person_name(tx.payer_person_id, persons),
            }

    tx_info = await execute_use_case(_fetch)

    new_split = f"{payer_percentage}/{100 - payer_percentage}"
    description = (
        f"Change {tx_info['merchant']} ({tx_info['date']}) "
        f"split from {tx_info['current_split']} to {new_split}"
    )
    details: dict[str, object] = {
        "transaction_id": str(transaction_id),
        "merchant": tx_info["merchant"],
        "date": tx_info["date"],
        "amount": tx_info["amount"],
        "payer": tx_info["payer"],
        "current_split": tx_info["current_split"],
        "new_split": new_split,
        "payer_percentage": payer_percentage,
    }
    return _propose_action(
        current_user, "update_transaction_split", tool_input, description, details
    )


async def handle_bulk_update_transactions(
    tool_input: dict[str, object],
    current_user: Person,
    _persons: list[Person],
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
        current_user, "bulk_update_transactions", tool_input, description, details
    )
