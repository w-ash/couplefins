from uuid import UUID

from pydantic import BaseModel

from src.application.use_cases.upload_csv import UploadCsvResult


class UploadSummaryResponse(BaseModel):
    upload_id: UUID
    filename: str
    period_year: int
    period_month: int
    total_transactions: int
    shared_count: int
    personal_count: int
    unmapped_categories: list[str]

    @classmethod
    def from_result(cls, result: UploadCsvResult) -> UploadSummaryResponse:
        return cls(
            upload_id=result.upload_id,
            filename=result.filename,
            period_year=result.period_year,
            period_month=result.period_month,
            total_transactions=result.total_transactions,
            shared_count=result.shared_count,
            personal_count=result.personal_count,
            unmapped_categories=result.unmapped_categories,
        )
