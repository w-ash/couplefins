from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter

from src.application.runner import execute_use_case
from src.application.use_cases.get_transaction_edits import (
    GetTransactionEditsCommand,
    GetTransactionEditsUseCase,
)
from src.application.use_cases.update_transaction import (
    UpdateTransactionCommand,
    UpdateTransactionUseCase,
)
from src.application.use_cases.update_transaction_splits import (
    SplitEntry,
    UpdateTransactionSplitsCommand,
    UpdateTransactionSplitsUseCase,
)
from src.interface.api.schemas.transactions import (
    TransactionEditHistoryResponse,
    TransactionEditResponse,
    UpdateSplitsRequest,
    UpdateSplitsResponse,
    UpdateTransactionRequest,
    UpdateTransactionResponse,
)

router = APIRouter(tags=["transactions"])


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
    return UpdateSplitsResponse(updated_count=result.updated_count)


@router.patch("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: UUID, body: UpdateTransactionRequest
) -> UpdateTransactionResponse:
    command = UpdateTransactionCommand(
        transaction_id=transaction_id,
        date=body.date,
        amount=Decimal(str(body.amount)) if body.amount is not None else None,
        category=body.category,
        tags=tuple(body.tags) if body.tags is not None else None,
        **(
            {"payer_percentage": body.payer_percentage}
            if "payer_percentage" in body.model_fields_set
            else {}
        ),
    )
    result = await execute_use_case(
        lambda uow: UpdateTransactionUseCase().execute(command, uow)
    )
    return UpdateTransactionResponse(
        id=result.transaction.id,
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
