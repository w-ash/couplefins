"""Execute chat tools by dispatching to existing use cases.

Each tool call runs its own execute_use_case() with a fresh UoW,
matching the existing pattern where use cases own their transaction
boundaries. Results are projected into concise summary dicts — not
raw entity dumps.
"""

from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from src.application.runner import execute_use_case
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
            "date": t.date.isoformat(),
            "merchant": t.merchant,
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
}
