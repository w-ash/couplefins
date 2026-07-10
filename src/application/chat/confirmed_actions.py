"""Confirmed-mutation executors — run a claimed PendingAction's use case.

Dispatch lives in registry.py: each write ToolSpec binds its executor here.
All executors share the (action, current_user) signature so the registry can
call them uniformly.
"""

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
from src.application.use_cases.bulk_update_mappings import (
    BulkUpdateMappingsCommand,
    BulkUpdateMappingsUseCase,
    MappingEntry,
)
from src.application.use_cases.bulk_update_transactions import (
    BulkUpdateTransactionsCommand,
    Unset,
    apply_bulk_transaction_updates,
)
from src.application.use_cases.copy_budgets import (
    CopyBudgetsCommand,
    CopyBudgetsUseCase,
)
from src.application.use_cases.create_category_group import (
    CreateCategoryGroupCommand,
    CreateCategoryGroupUseCase,
)
from src.application.use_cases.create_settlement_merchant import (
    CreateSettlementMerchantCommand,
    CreateSettlementMerchantUseCase,
)
from src.application.use_cases.delete_budget import (
    DeleteBudgetCommand,
    DeleteBudgetUseCase,
)
from src.application.use_cases.delete_category_group import (
    DeleteCategoryGroupCommand,
    DeleteCategoryGroupUseCase,
)
from src.application.use_cases.delete_settlement import (
    DeleteSettlementCommand,
    DeleteSettlementUseCase,
)
from src.application.use_cases.delete_settlement_merchant import (
    DeleteSettlementMerchantCommand,
    DeleteSettlementMerchantUseCase,
)
from src.application.use_cases.finalize_period import (
    FinalizePeriodCommand,
    FinalizePeriodUseCase,
)
from src.application.use_cases.list_category_groups import (
    ListCategoryGroupsCommand,
    ListCategoryGroupsUseCase,
)
from src.application.use_cases.mark_transaction_as_settlement import (
    MarkTransactionAsSettlementCommand,
    MarkTransactionAsSettlementUseCase,
)
from src.application.use_cases.record_settlement import (
    RecordSettlementCommand,
    RecordSettlementUseCase,
)
from src.application.use_cases.record_waived_settlement import (
    RecordWaivedSettlementCommand,
    RecordWaivedSettlementUseCase,
)
from src.application.use_cases.save_budget import (
    SaveBudgetCommand,
    SaveBudgetUseCase,
)
from src.application.use_cases.unfinalize_period import (
    UnfinalizePeriodCommand,
    UnfinalizePeriodUseCase,
)
from src.application.use_cases.unlink_settlement_transaction import (
    UnlinkSettlementTransactionCommand,
    UnlinkSettlementTransactionUseCase,
)
from src.application.use_cases.update_category import (
    UpdateCategoryCommand,
    UpdateCategoryUseCase,
)
from src.application.use_cases.update_category_group import (
    UpdateCategoryGroupCommand,
    UpdateCategoryGroupUseCase,
)
from src.application.use_cases.update_transaction_splits import (
    SplitEntry,
    UpdateTransactionSplitsCommand,
    UpdateTransactionSplitsUseCase,
)
from src.domain.entities.person import Person
from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


def _strip_user_data(value: str) -> str:
    """Undo the <user_data> labeling on values echoed through details."""
    return value.removeprefix("<user_data>").removesuffix("</user_data>")


async def exec_budget(
    action: PendingAction, _current_user: Person
) -> dict[str, object]:
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


async def exec_split(action: PendingAction, current_user: Person) -> dict[str, object]:
    splits = cast(list[dict[str, object]], action.details["splits"])
    command = UpdateTransactionSplitsCommand(
        splits=[
            SplitEntry(
                transaction_id=UUID(cast(str, entry["transaction_id"])),
                payer_percentage=cast(int, entry["payer_percentage"]),
            )
            for entry in splits
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


async def exec_bulk(action: PendingAction, current_user: Person) -> dict[str, object]:
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


async def exec_delete_budget(
    action: PendingAction, current_user: Person
) -> dict[str, object]:
    command = DeleteBudgetCommand(
        budget_id=UUID(cast(str, action.details["budget_id"])),
        person_id=current_user.id,
    )
    # The use case re-checks existence, ownership, and finalization —
    # the TOCTOU guard between propose and confirm.
    await execute_use_case(lambda uow: DeleteBudgetUseCase().execute(command, uow))
    return {"status": "confirmed", "description": action.description}


async def exec_copy_budgets(
    action: PendingAction, current_user: Person
) -> dict[str, object]:
    details = action.details
    command = CopyBudgetsCommand(
        source_year=cast(int, details["from_year"]),
        source_month=cast(int, details["from_month"]),
        target_year=cast(int, details["to_year"]),
        target_month=cast(int, details["to_month"]),
        person_id=current_user.id,
    )
    # Recomputed at confirm time: budgets added since propose are skipped,
    # not overwritten, and the target-month lock is re-checked.
    result = await execute_use_case(
        lambda uow: CopyBudgetsUseCase().execute(command, uow)
    )
    return {
        "status": "confirmed",
        "description": action.description,
        "copied_count": result.copied_count,
        "skipped_count": result.skipped_count,
    }


async def exec_category_group(
    action: PendingAction, _current_user: Person
) -> dict[str, object]:
    details = action.details
    action_kind = cast(str, details["action"])
    summary: dict[str, object] = {
        "status": "confirmed",
        "description": action.description,
    }
    if action_kind == "create":
        create_command = CreateCategoryGroupCommand(name=cast(str, details["name"]))
        create_result = await execute_use_case(
            lambda uow: CreateCategoryGroupUseCase().execute(create_command, uow)
        )
        summary["group_id"] = str(create_result.group.id)
    elif action_kind == "rename":
        group_id = UUID(cast(str, details["group_id"]))
        # The update evolves name AND icon together — preserve the icon by
        # reading the current group first (re-checks existence too).
        groups = await execute_use_case(
            lambda uow: ListCategoryGroupsUseCase().execute(
                ListCategoryGroupsCommand(), uow
            )
        )
        existing = next(
            (item.group for item in groups.items if item.group.id == group_id), None
        )
        if existing is None:
            raise ValidationError("Category group no longer exists")
        update_command = UpdateCategoryGroupCommand(
            id=group_id,
            name=cast(str, details["new_name"]),
            icon=existing.icon,
        )
        await execute_use_case(
            lambda uow: UpdateCategoryGroupUseCase().execute(update_command, uow)
        )
    else:  # delete
        move_to = cast(str | None, details.get("move_to_group_id"))
        delete_command = DeleteCategoryGroupCommand(
            group_id=UUID(cast(str, details["group_id"])),
            move_categories_to=UUID(move_to) if move_to else None,
        )
        await execute_use_case(
            lambda uow: DeleteCategoryGroupUseCase().execute(delete_command, uow)
        )
    return summary


async def exec_map_categories(
    action: PendingAction, _current_user: Person
) -> dict[str, object]:
    mappings = cast(list[dict[str, object]], action.details["mappings"])
    command = BulkUpdateMappingsCommand(
        mappings=[
            MappingEntry(
                category=_strip_user_data(cast(str, entry["category"])),
                group_id=UUID(cast(str, entry["group_id"])),
            )
            for entry in mappings
        ]
    )
    # The use case re-validates every group id at confirm time.
    result = await execute_use_case(
        lambda uow: BulkUpdateMappingsUseCase().execute(command, uow)
    )
    return {
        "status": "confirmed",
        "description": action.description,
        "updated_count": result.updated_count,
    }


async def exec_category_personal(
    action: PendingAction, _current_user: Person
) -> dict[str, object]:
    details = action.details
    command = UpdateCategoryCommand(
        name=_strip_user_data(cast(str, details["category"])),
        include_personal=cast(bool, details["new"]),
    )
    # NotFoundError from the use case is the TOCTOU guard.
    await execute_use_case(lambda uow: UpdateCategoryUseCase().execute(command, uow))
    return {"status": "confirmed", "description": action.description}


async def exec_finalize(
    action: PendingAction, _current_user: Person
) -> dict[str, object]:
    details = action.details
    command = FinalizePeriodCommand(
        year=cast(int, details["year"]),
        month=cast(int, details["month"]),
        notes=cast(str, details.get("notes") or ""),
    )
    # Raises if the period was finalized between propose and confirm.
    result = await execute_use_case(
        lambda uow: FinalizePeriodUseCase().execute(command, uow)
    )
    return {
        "status": "confirmed",
        "description": action.description,
        "finalized_at": result.period.finalized_at.isoformat()
        if result.period.finalized_at
        else None,
    }


async def exec_unfinalize(
    action: PendingAction, _current_user: Person
) -> dict[str, object]:
    details = action.details
    command = UnfinalizePeriodCommand(
        year=cast(int, details["year"]),
        month=cast(int, details["month"]),
    )
    # Raises if the period is no longer finalized.
    await execute_use_case(lambda uow: UnfinalizePeriodUseCase().execute(command, uow))
    return {"status": "confirmed", "description": action.description}


async def exec_record_settlement(
    action: PendingAction, _current_user: Person
) -> dict[str, object]:
    details = action.details
    linked = cast(list[str], details.get("linked_transaction_ids") or [])
    command = RecordSettlementCommand(
        amount=Decimal(str(details["amount"])),
        from_person_id=UUID(cast(str, details["from_person_id"])),
        to_person_id=UUID(cast(str, details["to_person_id"])),
        method=cast(str, details.get("method") or ""),
        year=cast(int | None, details.get("year")),
        month=cast(int | None, details.get("month")),
        notes=_strip_user_data(cast(str, details.get("notes") or "")),
        linked_transaction_ids=[UUID(tid) for tid in linked],
    )
    # The use case re-validates persons, linked transactions (existence,
    # not-already-linked, same-payer), and month locks for linked months.
    result = await execute_use_case(
        lambda uow: RecordSettlementUseCase().execute(command, uow)
    )
    return {
        "status": "confirmed",
        "description": action.description,
        "settlement_id": str(result.settlement.id),
        "warnings": result.warnings,
    }


async def exec_waive_settlement(
    action: PendingAction, _current_user: Person
) -> dict[str, object]:
    details = action.details
    command = RecordWaivedSettlementCommand(
        from_person_id=UUID(cast(str, details["from_person_id"])),
        to_person_id=UUID(cast(str, details["to_person_id"])),
        notes=_strip_user_data(cast(str, details.get("notes") or "")),
    )
    # The use case recomputes the ledger: a balance that settled or flipped
    # direction between propose and confirm is rejected, not double-waived.
    result = await execute_use_case(
        lambda uow: RecordWaivedSettlementUseCase().execute(command, uow)
    )
    return {
        "status": "confirmed",
        "description": action.description,
        "settlement_id": str(result.settlement.id),
        "waived_amount": float(result.settlement.amount),
        "warnings": result.warnings,
    }


async def exec_delete_settlement(
    action: PendingAction, _current_user: Person
) -> dict[str, object]:
    command = DeleteSettlementCommand(
        settlement_id=UUID(cast(str, action.details["settlement_id"]))
    )
    # Re-checks existence and the month locks of linked transactions.
    await execute_use_case(lambda uow: DeleteSettlementUseCase().execute(command, uow))
    return {"status": "confirmed", "description": action.description}


async def exec_link_settlement_tx(
    action: PendingAction, _current_user: Person
) -> dict[str, object]:
    details = action.details
    raw_settlement = cast(str | None, details.get("settlement_id"))
    command = MarkTransactionAsSettlementCommand(
        transaction_id=UUID(cast(str, details["transaction_id"])),
        settlement_id=UUID(raw_settlement) if raw_settlement else None,
        is_settlement=True,
    )
    # Re-checks existence, not-already-linked, and the month lock.
    await execute_use_case(
        lambda uow: MarkTransactionAsSettlementUseCase().execute(command, uow)
    )
    return {"status": "confirmed", "description": action.description}


async def exec_unlink_settlement_tx(
    action: PendingAction, _current_user: Person
) -> dict[str, object]:
    details = action.details
    command = UnlinkSettlementTransactionCommand(
        settlement_id=UUID(cast(str, details["settlement_id"])),
        transaction_id=UUID(cast(str, details["transaction_id"])),
    )
    result = await execute_use_case(
        lambda uow: UnlinkSettlementTransactionUseCase().execute(command, uow)
    )
    if not result.unlinked:
        # The link disappeared between propose and confirm — report it
        # rather than pretending the confirmation changed anything.
        raise ValidationError("That transaction is no longer linked")
    return {"status": "confirmed", "description": action.description}


async def exec_settlement_merchant(
    action: PendingAction, _current_user: Person
) -> dict[str, object]:
    details = action.details
    summary: dict[str, object] = {
        "status": "confirmed",
        "description": action.description,
    }
    if cast(str, details["action"]) == "add":
        create_command = CreateSettlementMerchantCommand(
            name=cast(str, details["raw_name"]),
            merchant_pattern=cast(str, details["raw_pattern"]),
        )
        create_result = await execute_use_case(
            lambda uow: CreateSettlementMerchantUseCase().execute(create_command, uow)
        )
        summary["merchant_id"] = str(create_result.merchant.id)
    else:  # remove
        delete_command = DeleteSettlementMerchantCommand(
            merchant_id=UUID(cast(str, details["merchant_id"]))
        )
        await execute_use_case(
            lambda uow: DeleteSettlementMerchantUseCase().execute(delete_command, uow)
        )
    return summary
