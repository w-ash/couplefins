from decimal import Decimal
from uuid import UUID

from attrs import define

from src.domain.month_key import assert_month_key


@define(frozen=True, slots=True)
class SettlementPortion:
    """One month's slice of a settlement payment.

    A settlement's portions record exactly which months it covers and with
    how much — they sum to the settlement amount and are allocated once, at
    record time. Display math only ever adds them up.

    The amount is signed: negative where the payment covers a month that ran
    the other way, taking value back from it to settle the covered span as a
    whole.
    """

    id: UUID
    settlement_id: UUID
    year: int
    month: int
    amount: Decimal

    def __attrs_post_init__(self) -> None:
        assert_month_key(self.year, self.month)
        if self.amount == 0:
            raise ValueError("amount must be non-zero")
