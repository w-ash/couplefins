from datetime import UTC, datetime

from fastapi import APIRouter

from src.application.runner import execute_use_case
from src.application.use_cases.get_dashboard import (
    GetDashboardCommand,
    GetDashboardUseCase,
)
from src.interface.api.schemas.dashboard import DashboardResponse

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def get_dashboard(
    year: int | None = None, month: int | None = None
) -> DashboardResponse:
    now = datetime.now(UTC)
    command = GetDashboardCommand(year=year or now.year, month=month or now.month)
    result = await execute_use_case(
        lambda uow: GetDashboardUseCase().execute(command, uow)
    )
    return DashboardResponse.from_result(result)
