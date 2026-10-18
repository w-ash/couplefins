from uuid import UUID

from fastapi import APIRouter, Depends

from src.application.runner import execute_use_case
from src.application.use_cases.delete_manual_transaction import (
    DeleteManualTransactionCommand,
    DeleteManualTransactionUseCase,
)
from src.application.use_cases.get_co_owned_asset import (
    GetCoOwnedAssetCommand,
    GetCoOwnedAssetUseCase,
)
from src.application.use_cases.get_house import GetHouseCommand, GetHouseUseCase
from src.application.use_cases.list_manual_transactions import (
    ListManualTransactionsCommand,
    ListManualTransactionsUseCase,
)
from src.application.use_cases.record_manual_transaction import (
    RecordManualTransactionUseCase,
)
from src.application.use_cases.save_co_owned_asset import SaveCoOwnedAssetUseCase
from src.domain.entities.person import Person
from src.infrastructure.events.event_bus import event_bus
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.house import (
    CoOwnedAssetResponse,
    HouseResponse,
    ManualEntryResponse,
    RecordManualTransactionRequest,
    SaveCoOwnedAssetRequest,
)

router = APIRouter(tags=["house"], dependencies=[Depends(get_current_user)])


@router.get("/house")
async def get_house() -> HouseResponse:
    command = GetHouseCommand()
    result = await execute_use_case(lambda uow: GetHouseUseCase().execute(command, uow))
    return HouseResponse.from_result(result)


@router.get("/house/asset")
async def get_co_owned_asset() -> CoOwnedAssetResponse | None:
    command = GetCoOwnedAssetCommand()
    result = await execute_use_case(
        lambda uow: GetCoOwnedAssetUseCase().execute(command, uow)
    )
    return CoOwnedAssetResponse.from_domain(result.asset) if result.asset else None


@router.put("/house/asset")
async def save_co_owned_asset(body: SaveCoOwnedAssetRequest) -> CoOwnedAssetResponse:
    command = body.to_command()
    result = await execute_use_case(
        lambda uow: SaveCoOwnedAssetUseCase().execute(command, uow)
    )
    event_bus.broadcast("house")
    return CoOwnedAssetResponse.from_domain(result.asset)


@router.get("/house/manual-entries")
async def list_manual_entries() -> list[ManualEntryResponse]:
    command = ListManualTransactionsCommand()
    result = await execute_use_case(
        lambda uow: ListManualTransactionsUseCase().execute(command, uow)
    )
    return [ManualEntryResponse.from_domain(tx) for tx in result.transactions]


@router.post("/house/manual-entries", status_code=201)
async def record_manual_entry(
    body: RecordManualTransactionRequest,
    current_user: Person = Depends(get_current_user),
) -> ManualEntryResponse:
    command = body.to_command(entered_by=current_user.id)
    result = await execute_use_case(
        lambda uow: RecordManualTransactionUseCase().execute(command, uow)
    )
    event_bus.broadcast("house", "transactions", "accounts")  # first adds the account
    return ManualEntryResponse.from_domain(result.transaction)


@router.delete("/house/manual-entries/{transaction_id}")
async def delete_manual_entry(transaction_id: UUID) -> dict[str, bool]:
    command = DeleteManualTransactionCommand(transaction_id=transaction_id)
    result = await execute_use_case(
        lambda uow: DeleteManualTransactionUseCase().execute(command, uow)
    )
    event_bus.broadcast("house", "transactions")
    return {"deleted": result.deleted}
