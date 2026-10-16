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
from src.application.use_cases.list_accounts import (
    ListAccountsCommand,
    ListAccountsUseCase,
)
from src.application.use_cases.list_settlement_merchants import (
    ListSettlementMerchantsCommand,
    ListSettlementMerchantsUseCase,
)
from src.application.use_cases.mark_account_joint import (
    MarkAccountJointCommand,
    MarkAccountJointUseCase,
)
from src.application.use_cases.unmark_account_joint import (
    UnmarkAccountJointCommand,
    UnmarkAccountJointUseCase,
)
from src.infrastructure.events.event_bus import event_bus
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.accounts import (
    AccountResponse,
    AccountsResponse,
    MarkAccountJointRequest,
    MarkAccountJointResponse,
    UnmarkAccountJointResponse,
)
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


@router.get("/settings/accounts")
async def get_accounts() -> AccountsResponse:
    command = ListAccountsCommand()
    result = await execute_use_case(
        lambda uow: ListAccountsUseCase().execute(command, uow)
    )
    return AccountsResponse(
        accounts=[AccountResponse.from_domain(a) for a in result.accounts]
    )


@router.post("/settings/accounts/joint", status_code=201)
async def mark_account_joint(body: MarkAccountJointRequest) -> MarkAccountJointResponse:
    command = MarkAccountJointCommand(label=body.label)
    result = await execute_use_case(
        lambda uow: MarkAccountJointUseCase().execute(command, uow)
    )
    event_bus.broadcast("accounts")
    event_bus.broadcast("transactions")
    return MarkAccountJointResponse(
        account=AccountResponse.from_domain(result.account),
        moved_count=result.moved_count,
        dropped_count=result.dropped_count,
    )


# `path` lets a label hold a slash.
@router.delete("/settings/accounts/joint/{label:path}")
async def unmark_account_joint(label: str) -> UnmarkAccountJointResponse:
    command = UnmarkAccountJointCommand(label=label)
    result = await execute_use_case(
        lambda uow: UnmarkAccountJointUseCase().execute(command, uow)
    )
    event_bus.broadcast("accounts")
    event_bus.broadcast("transactions")
    return UnmarkAccountJointResponse(moved_count=result.moved_count)
