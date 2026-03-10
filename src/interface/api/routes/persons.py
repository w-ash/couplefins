from fastapi import APIRouter

from src.application.runner import execute_use_case
from src.application.use_cases.list_persons import list_persons
from src.application.use_cases.setup_couple import (
    SetupCoupleCommand,
    SetupCoupleUseCase,
)
from src.interface.api.schemas.persons import PersonResponse, SetupCoupleRequest

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("/")
async def get_persons() -> list[PersonResponse]:
    persons = await execute_use_case(list_persons)
    return [PersonResponse.from_domain(p) for p in persons]


@router.post("/setup", status_code=201)
async def setup_couple(body: SetupCoupleRequest) -> list[PersonResponse]:
    command = SetupCoupleCommand(name1=body.name1, name2=body.name2)
    result = await execute_use_case(
        lambda uow: SetupCoupleUseCase(uow).execute(command)
    )
    return [PersonResponse.from_domain(p) for p in result.persons]
