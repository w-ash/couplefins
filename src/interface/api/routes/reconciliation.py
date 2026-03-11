from fastapi import APIRouter

from src.application.runner import execute_use_case
from src.application.use_cases.get_reconciliation import (
    GetReconciliationCommand,
    GetReconciliationUseCase,
)
from src.interface.api.schemas.reconciliation import ReconciliationResponse

router = APIRouter(tags=["reconciliation"])


@router.get("/reconciliation")
async def get_reconciliation(year: int, month: int) -> ReconciliationResponse:
    command = GetReconciliationCommand(year=year, month=month)
    result = await execute_use_case(
        lambda uow: GetReconciliationUseCase().execute(command, uow)
    )
    return ReconciliationResponse.from_result(result)
