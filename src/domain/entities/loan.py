"""A loan on the co-owned home, on the terms it was taken out on.

A loan's terms never change. A refinance replaces the loan with a new one,
and a loan no longer carried is closed; both keep the old loan and its
history. Only the servicer's statement balance and its date change in place:
the loan's balance re-anchors there (`src/domain/loans.py`).
"""

from datetime import date, datetime
from decimal import Decimal
import re
from typing import Final, Literal, get_args
import unicodedata
from uuid import UUID

from attrs import define

# How a payment splits into interest and principal. The named alias keeps
# its name in the API schema; the plain one gives the values at runtime.
_LoanKindValues = Literal["interest_only", "amortizing"]
type LoanKind = _LoanKindValues
LOAN_KINDS: tuple[LoanKind, ...] = get_args(_LoanKindValues)

# Lowercase letters and digits, with one hyphen between words.
_WORD: Final = re.compile(r"[a-z0-9]+")
_SLUG: Final = re.compile(rf"{_WORD.pattern}(?:-{_WORD.pattern})*")


def slugify(name: str) -> str:
    """The slug of a loan's name: its letters and digits in lowercase ASCII,
    each word joined to the next by one hyphen. Empty when the name holds
    no letter or digit."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore")
    return "-".join(_WORD.findall(ascii_name.decode().lower()))


@define(frozen=True, slots=True)
class Loan:
    """A loan on the co-owned asset.

    ``annual_rate`` is a percent (6.5 for 6.5%). ``slug`` comes from the
    name (`slugify`) and never changes: a payment row links to the loan by
    the tag `loan:<slug>`. ``statement_balance`` is the balance on the
    servicer's statement of ``statement_balance_as_of``. A replaced loan
    names its replacement in ``replaced_by_loan_id``; a replaced or closed
    loan has ``closed_on``, which can fall on any date: a bridge loan is
    often paid off before its first due date.
    """

    id: UUID
    asset_id: UUID
    name: str
    slug: str
    lender: str
    kind: LoanKind
    principal: Decimal
    annual_rate: Decimal
    payment: Decimal
    term_months: int | None
    first_due_on: date
    statement_balance: Decimal
    statement_balance_as_of: date
    replaced_by_loan_id: UUID | None
    closed_on: date | None
    notes: str
    created_at: datetime

    def __attrs_post_init__(self) -> None:
        for label, text in (("name", self.name), ("lender", self.lender)):
            if not text.strip():
                raise ValueError(f"{label} must not be empty")
        if not self.slug:
            raise ValueError("A loan's name must hold a letter or a digit")
        if _SLUG.fullmatch(self.slug) is None:
            raise ValueError(
                f"slug must be lowercase letters and digits joined by hyphens, "
                f"got {self.slug!r}"
            )
        for label, value in (("principal", self.principal), ("payment", self.payment)):
            if value <= 0:
                raise ValueError(f"{label} must be positive, got {value}")
        if self.annual_rate < 0:
            raise ValueError(
                f"annual_rate must not be negative, got {self.annual_rate}"
            )
        if self.statement_balance < 0:
            raise ValueError(
                f"statement_balance must not be negative, got {self.statement_balance}"
            )
        if self.term_months is not None and self.term_months <= 0:
            raise ValueError(f"term_months must be positive, got {self.term_months}")
        if self.replaced_by_loan_id is not None and self.closed_on is None:
            raise ValueError("A replaced loan must have closed_on")
        if self.replaced_by_loan_id == self.id:
            raise ValueError("A loan cannot replace itself")

    @property
    def is_open(self) -> bool:
        """True until the loan is closed or replaced."""
        return self.closed_on is None
