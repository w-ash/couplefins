from typing import Protocol
from uuid import UUID

from src.domain.entities.account import Account


class AccountRepositoryProtocol(Protocol):
    async def get_by_owner(self, owner_person_id: UUID) -> list[Account]: ...
    async def save_batch(self, entities: list[Account]) -> list[Account]: ...
