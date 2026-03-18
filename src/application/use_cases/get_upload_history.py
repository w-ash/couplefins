from datetime import date, datetime
from uuid import UUID

from attrs import define

from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetUploadHistoryCommand:
    """Parameterless — exists for API uniformity."""


@define(frozen=True, slots=True)
class UploadHistoryEntry:
    upload_id: UUID
    person_id: UUID
    person_name: str
    filename: str
    uploaded_at: datetime
    transaction_count: int
    shared_count: int
    date_range_start: date | None
    date_range_end: date | None


@define(frozen=True, slots=True)
class GetUploadHistoryResult:
    entries: list[UploadHistoryEntry]


@define(slots=True)
class GetUploadHistoryUseCase:
    async def execute(
        self, _command: GetUploadHistoryCommand, uow: UnitOfWorkProtocol
    ) -> GetUploadHistoryResult:
        async with uow:
            persons = await uow.persons.get_all()
            rows = await uow.uploads.get_all_with_transaction_counts()

        name_by_id = {p.id: p.name for p in persons}
        entries = [
            UploadHistoryEntry(
                upload_id=row.id,
                person_id=row.person_id,
                person_name=name_by_id.get(row.person_id, "Unknown"),
                filename=row.filename,
                uploaded_at=row.uploaded_at,
                transaction_count=row.transaction_count,
                shared_count=row.shared_count,
                date_range_start=row.date_range_start,
                date_range_end=row.date_range_end,
            )
            for row in rows
        ]
        return GetUploadHistoryResult(entries=entries)


async def get_upload_history(
    uow: UnitOfWorkProtocol,
) -> GetUploadHistoryResult:
    return await GetUploadHistoryUseCase().execute(GetUploadHistoryCommand(), uow)
