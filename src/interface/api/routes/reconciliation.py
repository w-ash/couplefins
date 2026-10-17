import datetime
from datetime import UTC
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from src.application.runner import execute_use_case
from src.application.use_cases._shared.transaction_reads import TagFilter
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
from src.domain.entities.person import Person
from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.infrastructure.events.event_bus import event_bus
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.reconciliation import (
    FinalizePeriodRequest,
    PeriodStatusResponse,
    ReconciliationQuery,
    ReconciliationResponse,
    UnfinalizePeriodRequest,
)

router = APIRouter(tags=["reconciliation"], dependencies=[Depends(get_current_user)])


@router.get("/reconciliation")
async def get_reconciliation(
    query: Annotated[ReconciliationQuery, Query()],
    current_user: Annotated[Person, Depends(get_current_user)],
) -> ReconciliationResponse:
    person_id = current_user.id if query.scope in {"personal", "all"} else None
    command = _build_command(query, person_id)
    result = await execute_use_case(
        lambda uow: GetReconciliationUseCase().execute(command, uow)
    )
    return ReconciliationResponse.from_result(result)


def _build_command(
    query: ReconciliationQuery, person_id: UUID | None
) -> GetReconciliationCommand:
    tag_filter = TagFilter(
        tags=tuple(query.tags) if query.tags else None, prefix=query.tag_prefix
    )
    start_date, end_date = query.start_date, query.end_date
    has_range = start_date is not None or end_date is not None
    has_ym = query.year is not None or query.month is not None

    if has_range and has_ym:
        raise ValidationError(
            "Provide either start_date/end_date or year/month, not both."
        )

    if has_range:
        if start_date is None or end_date is None:
            raise ValidationError("Both start_date and end_date are required.")
        if start_date > end_date:
            raise ValidationError("start_date must be <= end_date.")
        return GetReconciliationCommand.from_range(
            start_date,
            end_date,
            scope=query.scope,
            person_id=person_id,
            tag_filter=tag_filter,
        )

    now = datetime.datetime.now(UTC).date()
    return GetReconciliationCommand.from_month(
        query.year or now.year,
        query.month or now.month,
        scope=query.scope,
        person_id=person_id,
        tag_filter=tag_filter,
    )


@router.post("/reconciliation/finalize")
async def finalize_period(body: FinalizePeriodRequest) -> PeriodStatusResponse:
    command = FinalizePeriodCommand(year=body.year, month=body.month, notes=body.notes)
    result = await execute_use_case(
        lambda uow: FinalizePeriodUseCase().execute(command, uow)
    )
    event_bus.broadcast("reconciliation")
    return PeriodStatusResponse.from_domain(result.period)


@router.post("/reconciliation/unfinalize")
async def unfinalize_period(body: UnfinalizePeriodRequest) -> PeriodStatusResponse:
    command = UnfinalizePeriodCommand(year=body.year, month=body.month)
    result = await execute_use_case(
        lambda uow: UnfinalizePeriodUseCase().execute(command, uow)
    )
    event_bus.broadcast("reconciliation")
    return PeriodStatusResponse.from_domain(result.period)


@router.get("/reconciliation/period-status")
async def get_period_status(year: int, month: int) -> PeriodStatusResponse:

    async def _fetch(uow: UnitOfWorkProtocol) -> PeriodStatusResponse:
        async with uow:
            period = await uow.reconciliation_periods.get_by_period(year, month)
            return PeriodStatusResponse.from_domain(period)

    return await execute_use_case(_fetch)
