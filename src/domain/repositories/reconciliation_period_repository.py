from typing import Protocol
from uuid import UUID

from src.domain.entities.reconciliation_period import ReconciliationPeriod


class ReconciliationPeriodRepositoryProtocol(Protocol):
    async def get_by_id(self, id: UUID) -> ReconciliationPeriod | None: ...
    async def get_by_period(
        self, year: int, month: int
    ) -> ReconciliationPeriod | None: ...
    async def save(self, entity: ReconciliationPeriod) -> ReconciliationPeriod: ...
