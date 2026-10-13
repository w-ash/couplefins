from datetime import date
from typing import Protocol
from uuid import UUID

from src.domain.entities.upload import Upload, UploadWithCounts


class UploadRepositoryProtocol(Protocol):
    async def get_by_id(self, id: UUID) -> Upload | None: ...
    async def get_by_person_ids_with_transactions_in_period(
        self, person_ids: list[UUID], year: int, month: int
    ) -> list[Upload]: ...
    async def get_by_person_ids_with_transactions_in_date_range(
        self, person_ids: list[UUID], start_date: date, end_date: date
    ) -> list[Upload]: ...
    async def get_all_with_transaction_counts(self) -> list[UploadWithCounts]: ...
    async def save(self, entity: Upload) -> Upload: ...
