from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query

from src.application.runner import execute_use_case
from src.application.use_cases._shared.command_validators import Scope
from src.application.use_cases.get_dashboard import (
    GetDashboardCommand,
    GetDashboardUseCase,
)
from src.domain.entities.person import Person
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.dashboard import DashboardResponse

router = APIRouter(tags=["dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/dashboard")
async def get_dashboard(
    year: int | None = None,
    month: int | None = None,
    scope: Scope = Query("household"),
    current_user: Person = Depends(get_current_user),
) -> DashboardResponse:
    now = datetime.now(UTC)
    person_id = current_user.id if scope != "household" else None
    command = GetDashboardCommand(
        year=year or now.year, month=month, scope=scope, person_id=person_id
    )
    result = await execute_use_case(
        lambda uow: GetDashboardUseCase().execute(command, uow)
    )
    return DashboardResponse.from_result(result)
