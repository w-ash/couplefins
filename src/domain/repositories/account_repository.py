from typing import Protocol

from src.domain.entities.account import Account


class AccountRepositoryProtocol(Protocol):
    async def add_missing(self, entities: list[Account]) -> None: ...
