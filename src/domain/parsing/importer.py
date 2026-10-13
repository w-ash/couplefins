from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from attrs import define

from src.domain.entities.account import Account
from src.domain.entities.transaction import Transaction


@define(frozen=True, slots=True)
class ImportContext:
    """What an importer needs to know besides the file itself."""

    payer_person_id: UUID
    upload_id: UUID
    person_names: frozenset[str]


@define(frozen=True, slots=True)
class ParseResult:
    transactions: list[Transaction]
    skipped_adjustment_count: int


class Importer(Protocol):
    """Turns one source file into transactions for one uploader."""

    @property
    def name(self) -> str: ...

    def parse(self, data: bytes, ctx: ImportContext) -> ParseResult: ...


def accounts_named_by(transactions: Iterable[Transaction]) -> list[Account]:
    """Return the personal account each transaction names, once per account."""
    accounts = {
        tx.account_id: Account(
            id=tx.account_id,
            name=tx.account,
            kind="personal",
            owner_person_id=tx.payer_person_id,
        )
        for tx in transactions
    }
    return list(accounts.values())
