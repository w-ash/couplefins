from datetime import datetime
from decimal import Decimal
from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class Settlement:
    id: UUID
    # Optional "recorded against" annotation (v1.7.5) — display metadata for
    # human labels like "April rent". The ledger nets everything; these
    # fields never enter balance math.
    year: int | None
    month: int | None
    amount: Decimal
    from_person_id: UUID
    to_person_id: UUID
    method: str | None
    is_waived: bool
    notes: str
    settled_at: datetime
    created_at: datetime

    def __attrs_post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError(f"amount must be >= 0, got {self.amount}")
        if self.from_person_id == self.to_person_id:
            raise ValueError("from_person_id and to_person_id must differ")
        if (self.year is None) != (self.month is None):
            raise ValueError("year and month must be set together or not at all")
        max_month = 12
        if self.month is not None and not 1 <= self.month <= max_month:
            raise ValueError(f"month must be 1-{max_month}, got {self.month}")
