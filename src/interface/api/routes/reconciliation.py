import datetime
from datetime import UTC

from fastapi import APIRouter, HTTPException

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
async def get_reconciliation(
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    year: int | None = None,
    month: int | None = None,
) -> ReconciliationResponse:
    command = _build_command(start_date, end_date, year, month)
    result = await execute_use_case(
        lambda uow: GetReconciliationUseCase().execute(command, uow)
    )
    return ReconciliationResponse.from_result(result)


def _build_command(
    start_date: datetime.date | None,
    end_date: datetime.date | None,
    year: int | None,
    month: int | None,
) -> GetReconciliationCommand:
    has_range = start_date is not None or end_date is not None
    has_ym = year is not None or month is not None

    if has_range and has_ym:
        raise HTTPException(
            status_code=422,
            detail="Provide either start_date/end_date or year/month, not both.",
        )

    if has_range:
        if start_date is None or end_date is None:
            raise HTTPException(
                status_code=422,
                detail="Both start_date and end_date are required.",
            )
        if start_date > end_date:
            raise HTTPException(
                status_code=422, detail="start_date must be <= end_date."
            )
        return GetReconciliationCommand.from_range(start_date, end_date)

    now = datetime.datetime.now(UTC).date()
    return GetReconciliationCommand.from_month(year or now.year, month or now.month)


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
