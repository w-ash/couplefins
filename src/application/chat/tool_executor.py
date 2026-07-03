"""Execute chat tools by dispatching to existing use cases.

Each tool call runs its own execute_use_case() with a fresh UoW,
matching the existing pattern where use cases own their transaction
boundaries. Results are projected into concise summary dicts — not
raw entity dumps.

Mutation tools (update_budget, update_transaction_split,
bulk_update_transactions) store a pending action and return a
confirmation prompt — they never execute directly. Execution happens
via the confirmation path in the route handler.
"""

import calendar
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from src.application.chat.pending_actions import pending_action_store
from src.application.runner import execute_use_case
from src.application.use_cases._shared.finalization import load_period_status
from src.application.use_cases.get_budget_overview import (
    GetBudgetOverviewCommand,
    GetBudgetOverviewResult,
    GetBudgetOverviewUseCase,
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
from src.application.use_cases.list_category_groups import (
    ListCategoryGroupsCommand,
    ListCategoryGroupsUseCase,
)
from src.application.use_cases.search_transactions import (
    SearchTransactionsCommand,
    SearchTransactionsResult,
    SearchTransactionsUseCase,
)
from src.domain.entities.person import Person
from src.domain.exceptions import ToolExecutionError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

type _ToolHandler = Callable[
    [dict[str, object], Person, list[Person]], Awaitable[dict[str, object]]
]


def _ensure_handler(
    name: str,
) -> _ToolHandler:
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        raise ToolExecutionError(f"Unknown tool: {name}")
    return handler


async def execute_tool(
    name: str,
    tool_input: dict[str, object],
    current_user: Person,
    persons: list[Person],
) -> dict[str, object]:
    """Dispatch a tool call to the appropriate use case and return a summary."""
    handler = _ensure_handler(name)
    try:
        return await handler(tool_input, current_user, persons)
    except ToolExecutionError:
        raise
    except Exception as e:
        raise ToolExecutionError(f"Tool '{name}' failed: {e}") from e


def _person_name(person_id: UUID, persons: list[Person]) -> str:
    for p in persons:
        if p.id == person_id:
            return p.name
    return "Unknown"


_MAX_PAYER_PERCENTAGE = 100
_MAX_BULK_TRANSACTIONS = 100


def _fmt(amount: Decimal) -> float:
    return float(round(amount, 2))


# --- Tool handlers ---


async def _handle_settlement_balance(
    tool_input: dict[str, object],
    _current_user: Person,
    persons: list[Person],
) -> dict[str, object]:
    command = GetSettleUpDataCommand(
        year=cast(int, tool_input["year"]),
        month=cast(int, tool_input["month"]),
    )
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
    # Payments can reverse the direction (overpayment) — the net debtor is
    # authoritative, not the gross one.
    if result.net_position:
        summary["net_from"] = _person_name(result.net_position.from_person_id, persons)
        summary["net_to"] = _person_name(result.net_position.to_person_id, persons)

    summary["uploads"] = [
        {"person": us.person_name, "uploaded": us.has_uploaded}
        for us in result.upload_statuses
    ]
    return summary


async def _handle_budget_overview(
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


async def _handle_search_transactions(
    tool_input: dict[str, object],
    _current_user: Person,
    persons: list[Person],
) -> dict[str, object]:
    group_id: UUID | None = None
    group_name = cast(str | None, tool_input.get("category_group"))
    if group_name:
        group_id = await _resolve_category_group_id(group_name)

    command = SearchTransactionsCommand(
        year=cast(int, tool_input["year"]),
        month=cast(int, tool_input["month"]),
        merchant=cast(str | None, tool_input.get("merchant")),
        category_group_id=group_id,
        tag=cast(str | None, tool_input.get("tag")),
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
            "merchant": f"<user_data>{t.merchant}</user_data>",
            "amount": _fmt(t.amount),
            "category": t.category,
            "payer": _person_name(t.payer_person_id, persons),
            "split": split,
            "household": t.household,
        })
    return {
        "total_count": result.total_count,
        "showing": len(txns),
        "transactions": txns,
    }


async def _resolve_category_group_id(name: str) -> UUID | None:
    result = await execute_use_case(
        lambda uow: ListCategoryGroupsUseCase().execute(
            ListCategoryGroupsCommand(), uow
        )
    )
    name_lower = name.lower()
    for item in result.items:
        if item.group.name.lower() == name_lower:
            return item.group.id
    return None


async def _handle_spending_by_group(
    tool_input: dict[str, object],
    current_user: Person,
    persons: list[Person],
) -> dict[str, object]:
    result = await _handle_budget_overview(tool_input, current_user, persons)
    groups_list = cast(list[dict[str, object]], result["groups"])
    groups: list[dict[str, object]] = [
        {"name": g["name"], "spent": g["spent"]} for g in groups_list
    ]
    return {
        "month": result["month"],
        "groups": groups,
        "total": result["total_spent"],
    }


async def _handle_spending_trends(
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


async def _handle_dashboard_status(
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


async def _handle_update_budget(
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


async def _handle_update_transaction_split(
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
                "merchant": tx.merchant,
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


async def _handle_bulk_update_transactions(
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


_TOOL_HANDLERS: dict[
    str,
    _ToolHandler,
] = {
    "get_settlement_balance": _handle_settlement_balance,
    "get_budget_overview": _handle_budget_overview,
    "search_transactions": _handle_search_transactions,
    "get_spending_by_group": _handle_spending_by_group,
    "get_spending_trends": _handle_spending_trends,
    "get_dashboard_status": _handle_dashboard_status,
    "update_budget": _handle_update_budget,
    "update_transaction_split": _handle_update_transaction_split,
    "bulk_update_transactions": _handle_bulk_update_transactions,
}
