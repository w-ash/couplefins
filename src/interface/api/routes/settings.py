from uuid import UUID

from fastapi import APIRouter, Depends

from src.application.runner import execute_use_case
from src.application.use_cases.create_settlement_merchant import (
    CreateSettlementMerchantCommand,
    CreateSettlementMerchantUseCase,
)
from src.application.use_cases.delete_settlement_merchant import (
    DeleteSettlementMerchantCommand,
    DeleteSettlementMerchantUseCase,
)
from src.application.use_cases.list_settlement_merchants import (
    ListSettlementMerchantsCommand,
    ListSettlementMerchantsUseCase,
)
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.settings import (
    CreateSettlementMerchantRequest,
    SettlementMerchantResponse,
)

router = APIRouter(tags=["settings"], dependencies=[Depends(get_current_user)])


@router.get("/settings/settlement-merchants")
async def get_settlement_merchants() -> list[SettlementMerchantResponse]:
    command = ListSettlementMerchantsCommand()
    result = await execute_use_case(
        lambda uow: ListSettlementMerchantsUseCase().execute(command, uow)
    )
    return [SettlementMerchantResponse.from_domain(m) for m in result.merchants]


@router.post("/settings/settlement-merchants", status_code=201)
async def post_settlement_merchant(
    body: CreateSettlementMerchantRequest,
) -> SettlementMerchantResponse:
    command = CreateSettlementMerchantCommand(
        name=body.name,
        merchant_pattern=body.merchant_pattern,
    )
    result = await execute_use_case(
        lambda uow: CreateSettlementMerchantUseCase().execute(command, uow)
    )
    return SettlementMerchantResponse.from_domain(result.merchant)


@router.delete("/settings/settlement-merchants/{merchant_id}")
async def delete_settlement_merchant(merchant_id: UUID) -> dict[str, bool]:
    command = DeleteSettlementMerchantCommand(merchant_id=merchant_id)
    result = await execute_use_case(
        lambda uow: DeleteSettlementMerchantUseCase().execute(command, uow)
    )
    return {"deleted": result.deleted}
