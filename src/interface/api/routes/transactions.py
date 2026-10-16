from collections.abc import Mapping
from typing import TypedDict
from uuid import UUID

from fastapi import APIRouter, Depends

from src.application.runner import execute_use_case
from src.application.use_cases.bulk_modify_tags import (
    BulkModifyTagsCommand,
    BulkModifyTagsUseCase,
)
from src.application.use_cases.bulk_update_transactions import (
    BulkUpdateTransactionsCommand,
    BulkUpdateTransactionsUseCase,
    Unset,
)
from src.application.use_cases.get_tags import GetTagsUseCase
from src.application.use_cases.get_transaction_edits import (
    GetTransactionEditsCommand,
    GetTransactionEditsUseCase,
)
from src.application.use_cases.update_transaction_splits import (
    SplitEntry,
    UpdateTransactionSplitsCommand,
    UpdateTransactionSplitsUseCase,
)
from src.domain.entities.person import Person
from src.infrastructure.events.event_bus import event_bus
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.transactions import (
    BulkModifyTagsRequest,
    BulkModifyTagsResponse,
    BulkUpdateRequest,
    BulkUpdateResponse,
    ImportEventResponse,
    TransactionChangesRequest,
    TransactionEditHistoryResponse,
    TransactionEditResponse,
    UpdateSplitsRequest,
    UpdateSplitsResponse,
    UpdateTransactionRequest,
    UpdateTransactionResponse,
)

router = APIRouter(tags=["transactions"], dependencies=[Depends(get_current_user)])


def _given[T](value: T | None) -> T | Unset:
    """A field's value, or Unset when the request leaves it out or null."""
    return Unset.UNSET if value is None else value


class _CommandFields(TypedDict):
    category: str | None
    notes: str | None
    payer_percentage: int | Unset
    household: bool | Unset
    is_excluded: bool | Unset
    depositor_person_id: UUID | Unset | None
    owner_shares: Mapping[UUID, int] | Unset | None


def _command_fields(body: TransactionChangesRequest) -> _CommandFields:
    """The update command's fields from either PATCH body. The joint-row
    fields are Unset when the request leaves them out; an explicit null is
    a value that clears the field."""
    sent = body.model_fields_set
    return _CommandFields(
        category=body.category,
        notes=body.notes,
        payer_percentage=_given(body.payer_percentage),
        household=_given(body.household),
        is_excluded=_given(body.is_excluded),
        depositor_person_id=(
            body.depositor_person_id if "depositor_person_id" in sent else Unset.UNSET
        ),
        owner_shares=body.owner_shares if "owner_shares" in sent else Unset.UNSET,
    )


@router.get("/tags")
async def get_tags() -> list[str]:
    result = await execute_use_case(lambda uow: GetTagsUseCase().execute(uow))
    return result.tags


@router.patch("/transactions/splits")
async def update_splits(
    body: UpdateSplitsRequest,
    current_user: Person = Depends(get_current_user),
) -> UpdateSplitsResponse:
    command = UpdateTransactionSplitsCommand(
        splits=[
            SplitEntry(
                transaction_id=entry.transaction_id,
                payer_percentage=entry.payer_percentage,
            )
            for entry in body.splits
        ],
        edited_by_person_id=current_user.id,
    )
    result = await execute_use_case(
        lambda uow: UpdateTransactionSplitsUseCase().execute(command, uow)
    )
    event_bus.broadcast("transactions")
    return UpdateSplitsResponse(updated_count=result.updated_count)


@router.patch("/transactions/bulk-update")
async def bulk_update_transactions(
    body: BulkUpdateRequest,
    current_user: Person = Depends(get_current_user),
) -> BulkUpdateResponse:
    command = BulkUpdateTransactionsCommand(
        transaction_ids=list(body.transaction_ids),
        edited_by_person_id=current_user.id,
        **_command_fields(body),
    )
    result = await execute_use_case(
        lambda uow: BulkUpdateTransactionsUseCase().execute(command, uow)
    )
    event_bus.broadcast("transactions")
    return BulkUpdateResponse(updated_count=result.updated_count)


@router.post("/transactions/bulk-tags")
async def bulk_modify_tags(
    body: BulkModifyTagsRequest,
    current_user: Person = Depends(get_current_user),
) -> BulkModifyTagsResponse:
    command = BulkModifyTagsCommand(
        transaction_ids=list(body.transaction_ids),
        action=body.action,
        tags=list(body.tags),
        edited_by_person_id=current_user.id,
    )
    result = await execute_use_case(
        lambda uow: BulkModifyTagsUseCase().execute(command, uow)
    )
    event_bus.broadcast("transactions")
    return BulkModifyTagsResponse(updated_count=result.updated_count)


@router.patch("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: UUID,
    body: UpdateTransactionRequest,
    current_user: Person = Depends(get_current_user),
) -> UpdateTransactionResponse:
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[transaction_id],
        date=body.date,
        amount=body.amount,
        tags=tuple(body.tags) if body.tags is not None else None,
        edited_by_person_id=current_user.id,
        **_command_fields(body),
    )
    result = await execute_use_case(
        lambda uow: BulkUpdateTransactionsUseCase().execute(command, uow)
    )
    event_bus.broadcast("transactions")
    return UpdateTransactionResponse(
        id=transaction_id,
        edits=[TransactionEditResponse.model_validate(e) for e in result.edits],
    )


@router.get("/transactions/{transaction_id}/edits")
async def get_transaction_edits(
    transaction_id: UUID,
) -> TransactionEditHistoryResponse:
    command = GetTransactionEditsCommand(transaction_id=transaction_id)
    result = await execute_use_case(
        lambda uow: GetTransactionEditsUseCase().execute(command, uow)
    )
    return TransactionEditHistoryResponse(
        import_event=ImportEventResponse.model_validate(result.import_event)
        if result.import_event
        else None,
        edits=[TransactionEditResponse.model_validate(e) for e in result.edits],
    )
