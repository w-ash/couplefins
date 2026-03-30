from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from src.application.runner import execute_use_case
from src.application.use_cases.delete_budget import (
    DeleteBudgetCommand,
    DeleteBudgetUseCase,
)
from src.application.use_cases.get_budget_overview import (
    GetBudgetOverviewCommand,
    GetBudgetOverviewUseCase,
)
from src.application.use_cases.list_budgets import list_budgets
from src.application.use_cases.save_budget import SaveBudgetCommand, SaveBudgetUseCase
from src.application.use_cases.update_budget import (
    UpdateBudgetCommand,
    UpdateBudgetUseCase,
)
from src.domain.entities.person import Person
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.budgets import (
    BudgetOverviewResponse,
    BudgetResponse,
    SaveBudgetRequest,
    UpdateBudgetRequest,
)

router = APIRouter(tags=["budgets"], dependencies=[Depends(get_current_user)])


@router.get("/budgets/overview")
async def get_budget_overview(
    year: int = Query(...),
    month: int = Query(...),
    scope: Literal["household", "personal"] = Query("household"),
    current_user: Person = Depends(get_current_user),
) -> BudgetOverviewResponse:
    person_id = current_user.id if scope == "personal" else None
    command = GetBudgetOverviewCommand(
        year=year, month=month, scope=scope, person_id=person_id
    )
    result = await execute_use_case(
        lambda uow: GetBudgetOverviewUseCase().execute(command, uow)
    )
    return BudgetOverviewResponse.from_result(result)


@router.get("/budgets")
async def get_budgets() -> list[BudgetResponse]:
    result = await execute_use_case(list_budgets)
    return [BudgetResponse.from_domain(b) for b in result.budgets]


@router.post("/budgets", status_code=201)
async def post_budget(
    body: SaveBudgetRequest,
    current_user: Person = Depends(get_current_user),
) -> BudgetResponse:
    person_id = current_user.id if body.is_personal else None
    command = SaveBudgetCommand(
        group_id=body.group_id,
        monthly_amount=body.monthly_amount,
        effective_from=body.effective_from,
        person_id=person_id,
    )
    result = await execute_use_case(
        lambda uow: SaveBudgetUseCase().execute(command, uow)
    )
    return BudgetResponse.from_domain(result.budget)


@router.put("/budgets/{budget_id}")
async def put_budget(budget_id: UUID, body: UpdateBudgetRequest) -> BudgetResponse:
    command = UpdateBudgetCommand(
        budget_id=budget_id, monthly_amount=body.monthly_amount
    )
    result = await execute_use_case(
        lambda uow: UpdateBudgetUseCase().execute(command, uow)
    )
    return BudgetResponse.from_domain(result.budget)


@router.delete("/budgets/{budget_id}", status_code=204)
async def delete_budget(budget_id: UUID) -> None:
    command = DeleteBudgetCommand(budget_id=budget_id)
    await execute_use_case(lambda uow: DeleteBudgetUseCase().execute(command, uow))
