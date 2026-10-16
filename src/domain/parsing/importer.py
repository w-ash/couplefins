from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from attrs import define

from src.domain.entities.account import Account
from src.domain.entities.person import Person
from src.domain.entities.transaction import Transaction
from src.domain.filters import is_joint_row, payer_of


@define(frozen=True, slots=True)
class ImportContext:
    """What an importer needs to know besides the file itself.

    `persons` is the couple; `joint_labels` are the source account labels
    marked joint, whose rows import with no payer.
    """

    payer_person_id: UUID
    upload_id: UUID
    persons: tuple[Person, ...]
    joint_labels: frozenset[str] = frozenset()

    @property
    def person_names(self) -> frozenset[str]:
        """Lowercased names of the other persons, for spotted detection."""
        return frozenset(
            p.name.lower() for p in self.persons if p.id != self.payer_person_id
        )


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
    """Return the personal account each personal row names, once per account.

    Joint rows name no account here: a joint account exists before its rows
    import, from marking its label joint.
    """
    accounts = {
        tx.account_id: Account(
            id=tx.account_id,
            name=tx.account,
            kind="personal",
            owner_person_id=payer_of(tx),
        )
        for tx in transactions
        if not is_joint_row(tx)
    }
    return list(accounts.values())
