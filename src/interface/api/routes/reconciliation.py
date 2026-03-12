from fastapi import APIRouter

from src.application.runner import execute_use_case
from src.application.use_cases.finalize_period import (
    FinalizePeriodCommand,
    FinalizePeriodUseCase,
)
from src.application.use_cases.get_reconciliation import (
    GetReconciliationCommand,
    GetReconciliationUseCase,
)
from src.application.use_cases.unfinalize_period import (
    UnfinalizePeriodCommand,
    UnfinalizePeriodUseCase,
)
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.interface.api.schemas.reconciliation import (
    FinalizePeriodRequest,
    PeriodStatusResponse,
    ReconciliationResponse,
    UnfinalizePeriodRequest,
)

router = APIRouter(tags=["reconciliation"])


@router.get("/reconciliation")
async def get_reconciliation(year: int, month: int) -> ReconciliationResponse:
    command = GetReconciliationCommand(year=year, month=month)
    result = await execute_use_case(
        lambda uow: GetReconciliationUseCase().execute(command, uow)
    )
    return ReconciliationResponse.from_result(result)


@router.post("/reconciliation/finalize")
async def finalize_period(body: FinalizePeriodRequest) -> PeriodStatusResponse:
    command = FinalizePeriodCommand(year=body.year, month=body.month, notes=body.notes)
    result = await execute_use_case(
        lambda uow: FinalizePeriodUseCase().execute(command, uow)
    )
    return PeriodStatusResponse.from_domain(result.period)


@router.post("/reconciliation/unfinalize")
async def unfinalize_period(body: UnfinalizePeriodRequest) -> PeriodStatusResponse:
    command = UnfinalizePeriodCommand(year=body.year, month=body.month)
    result = await execute_use_case(
        lambda uow: UnfinalizePeriodUseCase().execute(command, uow)
    )
    return PeriodStatusResponse.from_domain(result.period)


@router.get("/reconciliation/period-status")
async def get_period_status(year: int, month: int) -> PeriodStatusResponse:

    async def _fetch(uow: UnitOfWorkProtocol) -> PeriodStatusResponse:
        async with uow:
            period = await uow.reconciliation_periods.get_by_period(year, month)
            return PeriodStatusResponse.from_domain(period)

    return await execute_use_case(_fetch)
