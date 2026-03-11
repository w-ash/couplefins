import json
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, UploadFile

from src.application.runner import execute_use_case
from src.application.use_cases.preview_csv import PreviewCsvCommand, PreviewCsvUseCase
from src.application.use_cases.upload_csv import UploadCsvCommand, UploadCsvUseCase
from src.interface.api.schemas.uploads import (
    PreviewUploadResponse,
    UploadSummaryResponse,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/preview")
async def post_upload_preview(
    file: UploadFile,
    person_id: UUID = Form(),
) -> PreviewUploadResponse:
    csv_bytes = await file.read()
    csv_text = csv_bytes.decode("utf-8-sig")

    command = PreviewCsvCommand(csv_text=csv_text, person_id=person_id)
    result = await execute_use_case(
        lambda uow: PreviewCsvUseCase().execute(command, uow)
    )
    return PreviewUploadResponse.from_result(result)


@router.post("/", status_code=201)
async def post_upload(
    file: UploadFile,
    person_id: UUID = Form(),
    accepted_change_ids: str = Form(default="[]"),
) -> UploadSummaryResponse:
    csv_bytes = await file.read()
    csv_text = csv_bytes.decode("utf-8-sig")

    try:
        raw_ids: list[str] = json.loads(accepted_change_ids)  # pyright: ignore[reportAny]
        change_ids = frozenset(UUID(id_str) for id_str in raw_ids)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(422, "Invalid accepted_change_ids") from exc

    command = UploadCsvCommand(
        csv_text=csv_text,
        person_id=person_id,
        filename=file.filename or "upload.csv",
        accepted_change_ids=change_ids,
    )
    result = await execute_use_case(
        lambda uow: UploadCsvUseCase().execute(command, uow)
    )
    return UploadSummaryResponse.from_result(result)
