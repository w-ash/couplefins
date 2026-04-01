from decimal import Decimal
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
from src.infrastructure.events.event_bus import event_bus
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.transactions import (
    BulkModifyTagsRequest,
    BulkModifyTagsResponse,
    BulkUpdateRequest,
    BulkUpdateResponse,
    TransactionEditHistoryResponse,
    TransactionEditResponse,
    UpdateSplitsRequest,
    UpdateSplitsResponse,
    UpdateTransactionRequest,
    UpdateTransactionResponse,
)

router = APIRouter(tags=["transactions"], dependencies=[Depends(get_current_user)])


@router.get("/tags")
async def get_tags() -> list[str]:
    result = await execute_use_case(lambda uow: GetTagsUseCase().execute(uow))
    return result.tags


@router.patch("/transactions/splits")
async def update_splits(body: UpdateSplitsRequest) -> UpdateSplitsResponse:
    command = UpdateTransactionSplitsCommand(
        splits=[
            SplitEntry(
                transaction_id=entry.transaction_id,
                payer_percentage=entry.payer_percentage,
            )
            for entry in body.splits
        ]
    )
    result = await execute_use_case(
        lambda uow: UpdateTransactionSplitsUseCase().execute(command, uow)
    )
    event_bus.broadcast("transactions")
    return UpdateSplitsResponse(updated_count=result.updated_count)


@router.patch("/transactions/bulk-update")
async def bulk_update_transactions(body: BulkUpdateRequest) -> BulkUpdateResponse:
    kwargs: dict[str, object] = {}
    if body.payer_percentage is not None:
        kwargs["payer_percentage"] = body.payer_percentage
    if body.household is not None:
        kwargs["household"] = body.household
    if body.is_excluded is not None:
        kwargs["is_excluded"] = body.is_excluded
    command = BulkUpdateTransactionsCommand(
        transaction_ids=list(body.transaction_ids),
        category=body.category,
        notes=body.notes,
        **kwargs,  # type: ignore[arg-type]
    )
    result = await execute_use_case(
        lambda uow: BulkUpdateTransactionsUseCase().execute(command, uow)
    )
    event_bus.broadcast("transactions")
    return BulkUpdateResponse(updated_count=result.updated_count)


@router.post("/transactions/bulk-tags")
async def bulk_modify_tags(body: BulkModifyTagsRequest) -> BulkModifyTagsResponse:
    command = BulkModifyTagsCommand(
        transaction_ids=list(body.transaction_ids),
        action=body.action,
        tags=list(body.tags),
    )
    result = await execute_use_case(
        lambda uow: BulkModifyTagsUseCase().execute(command, uow)
    )
    event_bus.broadcast("transactions")
    return BulkModifyTagsResponse(updated_count=result.updated_count)


@router.patch("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: UUID, body: UpdateTransactionRequest
) -> UpdateTransactionResponse:
    extras: dict[str, object] = {}
    if "payer_percentage" in body.model_fields_set:
        extras["payer_percentage"] = body.payer_percentage
    if "household" in body.model_fields_set:
        extras["household"] = body.household
    if "is_excluded" in body.model_fields_set:
        extras["is_excluded"] = body.is_excluded
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[transaction_id],
        date=body.date,
        amount=Decimal(str(body.amount)) if body.amount is not None else None,
        category=body.category,
        notes=body.notes,
        tags=tuple(body.tags) if body.tags is not None else None,
        **extras,  # type: ignore[arg-type]
    )
    result = await execute_use_case(
        lambda uow: BulkUpdateTransactionsUseCase().execute(command, uow)
    )
    event_bus.broadcast("transactions")
    tx_id = (
        result.updated_transactions[0].id
        if result.updated_transactions
        else transaction_id
    )
    return UpdateTransactionResponse(
        id=tx_id,
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
        edits=[TransactionEditResponse.model_validate(e) for e in result.edits],
    )
