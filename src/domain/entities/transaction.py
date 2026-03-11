from datetime import date
from decimal import Decimal
from uuid import UUID

from attrs import define

from src.domain.constants import SplitDefaults


@define(frozen=True, slots=True)
class Transaction:
    id: UUID
    upload_id: UUID
    date: date
    merchant: str
    category: str
    account: str
    original_statement: str
    occurrence: int
    notes: str
    amount: Decimal
    tags: tuple[str, ...]
    payer_person_id: UUID
    payer_percentage: int | None

    def __attrs_post_init__(self) -> None:
        if self.payer_percentage is not None and not (
            0 <= self.payer_percentage <= SplitDefaults.MAX_PAYER_PERCENTAGE
        ):
            raise ValueError(
                f"payer_percentage must be 0-{SplitDefaults.MAX_PAYER_PERCENTAGE}, got {self.payer_percentage}"
            )

    @property
    def is_shared(self) -> bool:
        return self.payer_percentage is not None
