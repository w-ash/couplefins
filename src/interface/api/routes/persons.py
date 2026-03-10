from fastapi import APIRouter

from src.application.runner import execute_use_case
from src.application.use_cases.create_person import (
    CreatePersonCommand,
    CreatePersonUseCase,
)
from src.application.use_cases.list_persons import list_persons
from src.interface.api.schemas.persons import CreatePersonRequest, PersonResponse

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("/")
async def get_persons() -> list[PersonResponse]:
    persons = await execute_use_case(list_persons)
    return [PersonResponse.from_domain(p) for p in persons]


@router.post("/", status_code=201)
async def post_person(body: CreatePersonRequest) -> PersonResponse:
    command = CreatePersonCommand(
        name=body.name, adjustment_account=body.adjustment_account
    )
    result = await execute_use_case(
        lambda uow: CreatePersonUseCase(uow).execute(command)
    )
    return PersonResponse.from_domain(result.person)
