from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID

from attrs import define, field

from src.domain.split_rules import (
    check_owner_shares,
    check_payer_percentage,
    is_joint_payer,
)


def _freeze_shares(shares: Mapping[UUID, int] | None) -> Mapping[UUID, int] | None:
    return None if shares is None else MappingProxyType(dict(shares))


@define(frozen=True, slots=True)
class Transaction:
    id: UUID
    upload_id: UUID
    date: date
    merchant: str
    category: str
    account: str
    account_id: UUID
    original_statement: str
    occurrence: int
    notes: str
    amount: Decimal
    tags: tuple[str, ...]
    # None on a joint account's row: both owners' money paid it.
    payer_person_id: UUID | None
    payer_percentage: int = 100
    household: bool = False
    is_settlement: bool = False
    is_excluded: bool = False
    original_date: date | None = None
    original_amount: Decimal | None = None
    # Joint rows only: the owner whose deposit this is.
    depositor_person_id: UUID | None = None
    # Joint rows only: each owner's percentage, overriding the 50/50 default.
    # A read-only mapping, left out of the hash so the entity stays hashable.
    owner_shares: Mapping[UUID, int] | None = field(
        default=None, converter=_freeze_shares, hash=False
    )

    def __attrs_post_init__(self) -> None:
        check_payer_percentage(self.payer_percentage)
        if self.owner_shares is not None:
            check_owner_shares(self.owner_shares)
        if not is_joint_payer(self.payer_person_id) and (
            self.owner_shares is not None or self.depositor_person_id is not None
        ):
            raise ValueError("Only a joint row has owner_shares or a depositor")
