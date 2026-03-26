from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from src.application.runner import execute_use_case
from src.application.use_cases.get_spending_trends import (
    GetSpendingTrendsCommand,
    GetSpendingTrendsUseCase,
)
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.insights import SpendingTrendsResponse

router = APIRouter(tags=["insights"], dependencies=[Depends(get_current_user)])


@router.get("/insights/spending-trends")
async def get_spending_trends(
    year: int | None = None,
    month: int | None = None,
    comparison_year: int | None = None,
) -> SpendingTrendsResponse:
    now = datetime.now(UTC)
    command = GetSpendingTrendsCommand(
        year=year or now.year,
        month=month,
        comparison_year=comparison_year,
    )
    result = await execute_use_case(
        lambda uow: GetSpendingTrendsUseCase().execute(command, uow)
    )
    return SpendingTrendsResponse.from_result(result)
