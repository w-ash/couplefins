from pydantic import BaseModel

from src.domain.ledger import LedgerMonth, LedgerYear, MonthSettlementStatus
from src.domain.reconciliation import SettlementResult
from src.interface.api.schemas.reconciliation import (
    MonthSpanResponse,
    OwedAmountResponse,
)


class LedgerMonthResponse(BaseModel):
    """One month, fully precomputed: charged, paid, balance, status."""

    year: int
    month: int
    charged: OwedAmountResponse | None  # net of the month's charges' shares
    paid: OwedAmountResponse | None  # payments applied to this month
    balance: OwedAmountResponse | None  # charged - paid; None means settled
    status: MonthSettlementStatus
    # True when the balance direction differs from its year's — the UI names
    # the person only on such rows.
    runs_against_year: bool

    @classmethod
    def from_domain(cls, month: LedgerMonth) -> LedgerMonthResponse:
        return cls(
            year=month.year,
            month=month.month,
            charged=owed(month.charged),
            paid=owed(month.paid),
            balance=owed(month.balance),
            status=month.status,
            runs_against_year=month.runs_against_year,
        )


class LedgerYearResponse(BaseModel):
    """One calendar year's totals — rendered as-is by both settlement cards."""

    year: int
    charged: OwedAmountResponse | None
    paid: OwedAmountResponse | None
    balance: OwedAmountResponse | None
    span: MonthSpanResponse | None  # (oldest, newest) charged month

    @classmethod
    def from_domain(cls, row: LedgerYear) -> LedgerYearResponse:
        return cls(
            year=row.year,
            charged=owed(row.charged),
            paid=owed(row.paid),
            balance=owed(row.balance),
            span=MonthSpanResponse.from_optional_span(row.span),
        )


def owed(result: SettlementResult | None) -> OwedAmountResponse | None:
    return None if result is None else OwedAmountResponse.from_domain(result)
