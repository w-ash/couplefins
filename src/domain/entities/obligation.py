"""A payment that comes due on the co-owned home.

An obligation is entered by hand, or generated from a loan's schedule. It
is paid once a transaction is linked to it; until then it is due, and late
after its delinquency date (`src/domain/obligations.py`).
"""

from datetime import date
from decimal import Decimal
from typing import Literal, get_args
from uuid import UUID

from attrs import define

# What an obligation pays for. The named alias keeps its name in the API
# schema; the plain one gives the values at runtime.
_ObligationKindValues = Literal["loan_payment", "property_tax", "insurance", "other"]
type ObligationKind = _ObligationKindValues
OBLIGATION_KINDS: tuple[ObligationKind, ...] = get_args(_ObligationKindValues)

# Where an obligation stands on a given day. Computed, never stored.
type ObligationStatus = Literal["due", "paid", "late"]


@define(frozen=True, slots=True, kw_only=True)
class Obligation:
    """One payment due, and the pot or account that pays it.

    ``amount`` is what is due (> 0); ``is_estimate`` marks an amount not
    yet billed. ``late_after`` is the delinquency date, when there is one
    later than the due date. ``loan_id`` names the loan of a `loan_payment`
    and of no other kind. ``paid_by_transaction_id`` is the row that paid
    it, None while unpaid.
    """

    id: UUID
    asset_id: UUID
    kind: ObligationKind
    description: str
    amount: Decimal
    is_estimate: bool = False
    due_on: date
    late_after: date | None = None
    pays_from: str | None = None
    loan_id: UUID | None
    paid_by_transaction_id: UUID | None
    notes: str = ""

    def __attrs_post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("description must not be empty")
        if self.amount <= 0:
            raise ValueError(f"amount must be positive, got {self.amount}")
        if self.late_after is not None and self.late_after < self.due_on:
            raise ValueError("late_after must not be before due_on")
        if (self.kind == "loan_payment") != (self.loan_id is not None):
            raise ValueError("A loan payment needs its loan, and only a loan payment")

    @property
    def is_paid(self) -> bool:
        return self.paid_by_transaction_id is not None
