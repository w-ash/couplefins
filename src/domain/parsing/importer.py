from collections.abc import Mapping
from typing import Protocol
import uuid
from uuid import UUID

from attrs import define, field

from src.domain.entities.account import Account
from src.domain.entities.transaction import Transaction


@define(frozen=True, slots=True)
class ImportContext:
    """What an importer needs to know besides the file itself."""

    payer_person_id: UUID
    upload_id: UUID
    person_names: frozenset[str]
    # The uploader's accounts, by the label the source uses for each.
    accounts_by_label: Mapping[str, UUID]


@define(frozen=True, slots=True)
class ParseResult:
    transactions: list[Transaction]
    skipped_adjustment_count: int
    # Accounts the file names that the uploader does not have yet. Each
    # transaction's account_id points at one of these or at an existing account.
    new_accounts: list[Account]


@define(slots=True)
class AccountResolver:
    """Map an import's account labels to the uploader's accounts.

    A label the uploader has no account for gets a new personal account,
    created once and kept in `new_accounts` for the caller to save.
    """

    owner_person_id: UUID
    known: dict[str, UUID]
    new_accounts: list[Account] = field(factory=list)

    def id_for(self, label: str) -> UUID:
        if label not in self.known:
            account = Account(
                id=uuid.uuid4(),
                name=label,
                kind="personal",
                owner_person_id=self.owner_person_id,
            )
            self.known[label] = account.id
            self.new_accounts.append(account)
        return self.known[label]


class Importer(Protocol):
    """Turns one source file into transactions for one uploader."""

    @property
    def name(self) -> str: ...

    def parse(self, data: bytes, ctx: ImportContext) -> ParseResult: ...
