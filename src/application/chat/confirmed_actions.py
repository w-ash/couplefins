"""Execute confirmed chat mutations via the appropriate use cases."""

from decimal import Decimal
from typing import cast
from uuid import UUID

from src.application.chat.pending_actions import PendingAction
from src.application.runner import execute_use_case
from src.application.use_cases.bulk_modify_tags import (
    BulkModifyTagsCommand,
    BulkModifyTagsUseCase,
    TagAction,
)
from src.application.use_cases.bulk_update_transactions import (
    BulkUpdateTransactionsCommand,
    BulkUpdateTransactionsUseCase,
    Unset,
)
from src.application.use_cases.save_budget import (
    SaveBudgetCommand,
    SaveBudgetUseCase,
)
from src.application.use_cases.update_transaction_splits import (
    SplitEntry,
    UpdateTransactionSplitsCommand,
    UpdateTransactionSplitsUseCase,
)
from src.domain.entities.person import Person

ACTION_ENTITY_MAP: dict[str, str] = {
    "update_budget": "budgets",
    "update_transaction_split": "transactions",
    "bulk_update_transactions": "transactions",
}


async def execute_confirmed_action(
    action: PendingAction,
    current_user: Person,
) -> tuple[dict[str, object], str | None]:
    """Execute a confirmed pending action. Returns (result_summary, entity_to_broadcast)."""
    if action.tool_name == "update_budget":
        result = await _exec_budget(action)
    elif action.tool_name == "update_transaction_split":
        result = await _exec_split(action, current_user)
    elif action.tool_name == "bulk_update_transactions":
        result = await _exec_bulk(action, current_user)
    else:
        raise ValueError(f"Unknown mutation tool: {action.tool_name}")
    entity = ACTION_ENTITY_MAP.get(action.tool_name)
    return result, entity


async def _exec_budget(action: PendingAction) -> dict[str, object]:
    details = action.details
    group_id = UUID(cast(str, details["group_id"]))
    person_id = (
        UUID(cast(str, details["person_id"])) if details.get("person_id") else None
    )
    command = SaveBudgetCommand(
        group_id=group_id,
        monthly_amount=Decimal(str(details["amount"])),
        year=cast(int, details["year"]),
        month=cast(int, details["month"]),
        person_id=person_id,
    )
    result = await execute_use_case(
        lambda uow: SaveBudgetUseCase().execute(command, uow)
    )
    return {
        "status": "confirmed",
        "description": action.description,
        "budget_id": str(result.budget.id),
    }


async def _exec_split(action: PendingAction, current_user: Person) -> dict[str, object]:
    details = action.details
    command = UpdateTransactionSplitsCommand(
        splits=[
            SplitEntry(
                transaction_id=UUID(cast(str, details["transaction_id"])),
                payer_percentage=cast(int, details["payer_percentage"]),
            )
        ],
        edited_by_person_id=current_user.id,
    )
    result = await execute_use_case(
        lambda uow: UpdateTransactionSplitsUseCase().execute(command, uow)
    )
    return {
        "status": "confirmed",
        "description": action.description,
        "updated_count": result.updated_count,
    }


async def _exec_bulk(action: PendingAction, current_user: Person) -> dict[str, object]:
    details = action.details
    raw_ids = cast(list[str], details["transaction_ids"])
    transaction_ids = [UUID(tid) for tid in raw_ids]
    changes = cast(dict[str, object], details["changes"])

    results: list[dict[str, object]] = []

    if "tags" in changes:
        tag_info = cast(dict[str, object], changes["tags"])
        tag_command = BulkModifyTagsCommand(
            transaction_ids=transaction_ids,
            action=TagAction(cast(str, tag_info["action"])),
            tags=cast(list[str], tag_info["values"]),
            edited_by_person_id=current_user.id,
        )
        tag_result = await execute_use_case(
            lambda uow: BulkModifyTagsUseCase().execute(tag_command, uow)
        )
        results.append({"tags_updated": tag_result.updated_count})

    field_changes = {k: v for k, v in changes.items() if k != "tags"}
    if field_changes:
        field_command = BulkUpdateTransactionsCommand(
            transaction_ids=transaction_ids,
            edited_by_person_id=current_user.id,
            household=cast(bool, field_changes["household"])
            if "household" in field_changes
            else Unset.UNSET,
            payer_percentage=cast(int, field_changes["payer_percentage"])
            if "payer_percentage" in field_changes
            else Unset.UNSET,
            is_excluded=cast(bool, field_changes["is_excluded"])
            if "is_excluded" in field_changes
            else Unset.UNSET,
            category=cast(str, field_changes["category"])
            if "category" in field_changes
            else None,
        )
        field_result = await execute_use_case(
            lambda uow: BulkUpdateTransactionsUseCase().execute(field_command, uow)
        )
        results.append({"fields_updated": field_result.updated_count})

    total = sum(
        cast(int, r.get("tags_updated", 0)) + cast(int, r.get("fields_updated", 0))
        for r in results
    )
    return {
        "status": "confirmed",
        "description": action.description,
        "updated_count": total,
    }
