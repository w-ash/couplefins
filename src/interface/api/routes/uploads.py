import json
from uuid import UUID

from fastapi import APIRouter, Depends, Form, UploadFile

from src.application.runner import execute_use_case
from src.application.use_cases.get_upload_history import get_upload_history
from src.application.use_cases.preview_csv import PreviewCsvCommand, PreviewCsvUseCase
from src.application.use_cases.upload_csv import UploadCsvCommand, UploadCsvUseCase
from src.domain.exceptions import ValidationError
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.uploads import (
    PreviewUploadResponse,
    UploadHistoryResponse,
    UploadSummaryResponse,
)

router = APIRouter(
    prefix="/uploads",
    tags=["uploads"],
    dependencies=[Depends(get_current_user)],
)


async def _decode_csv(file: UploadFile) -> str:
    csv_bytes = await file.read()
    try:
        return csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError(
            "File is not valid UTF-8 text. Monarch exports use UTF-8 — try re-exporting."
        ) from exc


@router.get("/history")
async def upload_history() -> UploadHistoryResponse:
    result = await execute_use_case(get_upload_history)
    return UploadHistoryResponse.from_result(result)


@router.post("/preview")
async def post_upload_preview(
    file: UploadFile,
    person_id: UUID = Form(),
) -> PreviewUploadResponse:
    csv_text = await _decode_csv(file)

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
    csv_text = await _decode_csv(file)

    try:
        raw_ids: list[str] = json.loads(accepted_change_ids)  # pyright: ignore[reportAny]
        change_ids = frozenset(UUID(id_str) for id_str in raw_ids)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValidationError("Invalid accepted_change_ids") from exc

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
