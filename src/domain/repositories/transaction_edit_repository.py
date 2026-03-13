from typing import Protocol
from uuid import UUID

from src.domain.entities.transaction_edit import TransactionEdit


class TransactionEditRepositoryProtocol(Protocol):
    async def save_batch(
        self, entities: list[TransactionEdit]
    ) -> list[TransactionEdit]: ...
    async def get_by_transaction_id(
        self, transaction_id: UUID
    ) -> list[TransactionEdit]: ...
