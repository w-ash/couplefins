from fastapi import APIRouter, Depends, Query

from src.application.runner import execute_use_case
from src.application.use_cases._shared.command_validators import (
    PersonScope,
    person_for_scope,
)
from src.application.use_cases.get_spending_trends import (
    GetSpendingTrendsCommand,
    GetSpendingTrendsUseCase,
)
from src.domain.entities.person import Person
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.insights import SpendingTrendsResponse

router = APIRouter(tags=["insights"], dependencies=[Depends(get_current_user)])


@router.get("/insights/spending-trends")
async def get_spending_trends(
    year: int | None = None,
    month: int | None = None,
    comparison_year: int | None = None,
    scope: PersonScope = Query("household"),
    current_user: Person = Depends(get_current_user),
) -> SpendingTrendsResponse:
    command = GetSpendingTrendsCommand(
        year=year,
        month=month,
        comparison_year=comparison_year,
        scope=scope,
        person_id=person_for_scope(scope, current_user),
    )
    result = await execute_use_case(
        lambda uow: GetSpendingTrendsUseCase().execute(command, uow)
    )
    return SpendingTrendsResponse.from_result(result)
