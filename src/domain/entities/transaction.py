from datetime import date
from decimal import Decimal
from uuid import UUID

from attrs import define

from src.domain.splits import check_payer_percentage


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
    payer_percentage: int = 100
    household: bool = False
    is_settlement: bool = False
    is_excluded: bool = False
    original_date: date | None = None
    original_amount: Decimal | None = None

    def __attrs_post_init__(self) -> None:
        check_payer_percentage(self.payer_percentage)
