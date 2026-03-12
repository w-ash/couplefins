from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import Response

from src.application.runner import execute_use_case
from src.application.use_cases.export_adjustments import (
    ExportAdjustmentsCommand,
    ExportAdjustmentsUseCase,
    PreviewAdjustmentsUseCase,
)
from src.application.use_cases.list_persons import list_persons
from src.application.use_cases.setup_couple import (
    SetupCoupleCommand,
    SetupCoupleUseCase,
)
from src.application.use_cases.update_person import (
    UpdatePersonCommand,
    UpdatePersonUseCase,
)
from src.interface.api.schemas.persons import (
    AdjustmentPreviewResponse,
    PersonResponse,
    SetupCoupleRequest,
    UpdatePersonRequest,
)

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("/")
async def get_persons() -> list[PersonResponse]:
    result = await execute_use_case(list_persons)
    return [PersonResponse.from_domain(p) for p in result.persons]


@router.post("/setup", status_code=201)
async def setup_couple(body: SetupCoupleRequest) -> list[PersonResponse]:
    command = SetupCoupleCommand(name1=body.name1, name2=body.name2)
    result = await execute_use_case(
        lambda uow: SetupCoupleUseCase().execute(command, uow)
    )
    return [PersonResponse.from_domain(p) for p in result.persons]


@router.patch("/{person_id}")
async def update_person(person_id: UUID, body: UpdatePersonRequest) -> PersonResponse:
    command = UpdatePersonCommand(
        id=person_id, adjustment_account=body.adjustment_account
    )
    result = await execute_use_case(
        lambda uow: UpdatePersonUseCase().execute(command, uow)
    )
    return PersonResponse.from_domain(result.person)


@router.get("/{person_id}/adjustments/{year}/{month}")
async def preview_adjustments(
    person_id: UUID, year: int, month: int
) -> AdjustmentPreviewResponse:
    command = ExportAdjustmentsCommand(person_id=person_id, year=year, month=month)
    result = await execute_use_case(
        lambda uow: PreviewAdjustmentsUseCase().execute(command, uow)
    )
    return AdjustmentPreviewResponse.from_result(result)


@router.get("/{person_id}/export/{year}/{month}")
async def export_adjustments(person_id: UUID, year: int, month: int) -> Response:
    command = ExportAdjustmentsCommand(person_id=person_id, year=year, month=month)
    result = await execute_use_case(
        lambda uow: ExportAdjustmentsUseCase().execute(command, uow)
    )
    return Response(
        content=result.csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )
