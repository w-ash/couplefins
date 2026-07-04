"""Execute confirmed chat mutations via the appropriate use cases."""

from decimal import Decimal
from typing import cast
from uuid import UUID

from src.application.chat.pending_actions import PendingAction
from src.application.runner import execute_use_case
from src.application.use_cases.bulk_modify_tags import (
    BulkModifyTagsCommand,
    TagAction,
    apply_bulk_tag_changes,
)
from src.application.use_cases.bulk_update_transactions import (
    BulkUpdateTransactionsCommand,
    Unset,
    apply_bulk_transaction_updates,
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
from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

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
    """Run tag changes and field changes as one atomic operation.

    Both mutations run inside a single `execute_use_case` call — one UoW,
    one commit at the end — so a failing field update (e.g. an unknown
    category) rolls back an already-applied tag change instead of
    half-applying the confirmed action.
    """
    details = action.details
    raw_ids = cast(list[str], details["transaction_ids"])
    transaction_ids = [UUID(tid) for tid in raw_ids]
    changes = cast(dict[str, object], details["changes"])

    tag_command: BulkModifyTagsCommand | None = None
    if "tags" in changes:
        tag_info = cast(dict[str, object], changes["tags"])
        tag_command = BulkModifyTagsCommand(
            transaction_ids=transaction_ids,
            action=TagAction(cast(str, tag_info["action"])),
            tags=cast(list[str], tag_info["values"]),
            edited_by_person_id=current_user.id,
        )

    field_changes = {k: v for k, v in changes.items() if k != "tags"}
    field_command: BulkUpdateTransactionsCommand | None = None
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

    async def _run(uow: UnitOfWorkProtocol) -> tuple[int, int]:
        async with uow:
            tags_updated = 0
            fields_updated = 0
            if tag_command is not None:
                tag_result = await apply_bulk_tag_changes(tag_command, uow)
                tags_updated = tag_result.updated_count
            if field_command is not None:
                # Re-check category existence at confirm time (TOCTOU guard
                # mirroring the propose-time check in
                # tool_executor._check_category_exists) — this runs before
                # the shared commit, so an unknown category rolls back the
                # tag change above instead of half-applying.
                if field_command.category is not None:
                    existing = await uow.categories.get_by_name(field_command.category)
                    if existing is None:
                        raise ValidationError(
                            f"Unknown category: {field_command.category}"
                        )
                field_result = await apply_bulk_transaction_updates(field_command, uow)
                fields_updated = field_result.updated_count
            await uow.commit()
            return tags_updated, fields_updated

    tags_updated, fields_updated = await execute_use_case(_run)

    return {
        "status": "confirmed",
        "description": action.description,
        "updated_count": tags_updated + fields_updated,
    }
