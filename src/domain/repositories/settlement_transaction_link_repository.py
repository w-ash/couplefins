from typing import Protocol
from uuid import UUID

from src.domain.entities.settlement_transaction_link import SettlementTransactionLink


class SettlementTransactionLinkRepositoryProtocol(Protocol):
    async def save_batch(
        self, entities: list[SettlementTransactionLink]
    ) -> list[SettlementTransactionLink]: ...
    async def get_by_settlement_ids(
        self, settlement_ids: list[UUID]
    ) -> list[SettlementTransactionLink]: ...
    async def delete_by_settlement_id(self, settlement_id: UUID) -> int: ...
