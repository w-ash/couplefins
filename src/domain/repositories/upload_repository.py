from typing import Protocol
from uuid import UUID

from src.domain.entities.upload import Upload


class UploadRepositoryProtocol(Protocol):
    async def get_by_id(self, id: UUID) -> Upload | None: ...
    async def get_by_period(self, year: int, month: int) -> list[Upload]: ...
    async def save(self, entity: Upload) -> Upload: ...
