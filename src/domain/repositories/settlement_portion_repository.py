from typing import Protocol
from uuid import UUID

from src.domain.entities.settlement_portion import SettlementPortion


class SettlementPortionRepositoryProtocol(Protocol):
    async def save_batch(
        self, entities: list[SettlementPortion]
    ) -> list[SettlementPortion]: ...
    # All-time fetch for the settlement ledger.
    async def get_all(self) -> list[SettlementPortion]: ...
    async def delete_by_settlement_id(self, settlement_id: UUID) -> int: ...
