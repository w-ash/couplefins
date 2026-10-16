from fastapi import APIRouter, Depends

from src.application.runner import execute_use_case
from src.application.use_cases.get_house import GetHouseCommand, GetHouseUseCase
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.house import HouseResponse

router = APIRouter(tags=["house"], dependencies=[Depends(get_current_user)])


@router.get("/house")
async def get_house() -> HouseResponse:
    command = GetHouseCommand()
    result = await execute_use_case(lambda uow: GetHouseUseCase().execute(command, uow))
    return HouseResponse.from_result(result)
