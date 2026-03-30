import datetime
from datetime import UTC
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from src.application.runner import execute_use_case
from src.application.use_cases.finalize_period import (
    FinalizePeriodCommand,
    FinalizePeriodUseCase,
)
from src.application.use_cases.get_reconciliation import (
    GetReconciliationCommand,
    GetReconciliationUseCase,
    ReconciliationScope,
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
    ReconciliationResponse,
    UnfinalizePeriodRequest,
)

router = APIRouter(tags=["reconciliation"], dependencies=[Depends(get_current_user)])


@router.get("/reconciliation")
async def get_reconciliation(  # noqa: PLR0913, PLR0917
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    year: int | None = None,
    month: int | None = None,
    scope: str | None = None,
    tags: list[str] | None = Query(None),
    current_user: Person = Depends(get_current_user),
) -> ReconciliationResponse:
    person_id = current_user.id if scope in {"personal", "all"} else None
    command = _build_command(start_date, end_date, year, month, scope, person_id, tags)
    result = await execute_use_case(
        lambda uow: GetReconciliationUseCase().execute(command, uow)
    )
    return ReconciliationResponse.from_result(result)


_VALID_SCOPES: set[ReconciliationScope] = {"household", "personal", "all"}


def _build_command(  # noqa: PLR0913, PLR0917
    start_date: datetime.date | None,
    end_date: datetime.date | None,
    year: int | None,
    month: int | None,
    scope: str | None,
    person_id: UUID | None,
    tags: list[str] | None,
) -> GetReconciliationCommand:
    resolved_scope: ReconciliationScope = "household"
    if scope is not None:
        if scope not in _VALID_SCOPES:
            raise ValidationError(f"Invalid scope: {scope}")
        resolved_scope = scope  # type: ignore[assignment]

    resolved_tags = tuple(tags) if tags else None

    has_range = start_date is not None or end_date is not None
    has_ym = year is not None or month is not None

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
            scope=resolved_scope,
            person_id=person_id,
            tags=resolved_tags,
        )

    now = datetime.datetime.now(UTC).date()
    return GetReconciliationCommand.from_month(
        year or now.year,
        month or now.month,
        scope=resolved_scope,
        person_id=person_id,
        tags=resolved_tags,
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
