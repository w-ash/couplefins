"""Illustrative figures for Alice and Bob only. Nothing here is a real household's (CLAUDE.md: public repo).

The House page serves this payload until the real figures replace it, one
section at a time. Totals, percents, differences, and shortfalls come from the
domain functions that the real figures use, so the payload stays consistent
when one hand-written figure changes.
"""

import datetime
from decimal import Decimal
from uuid import UUID

from src.domain.house import (
    ActivityKind,
    ActivityRow,
    HouseFigures,
    HousePerson,
    LoanFigures,
    ObligationFigures,
    OwnerAmount,
    ShareHistoryPoint,
    bucket,
    put_in_section,
    set_aside_section,
    share_percentages,
    shares_section,
    with_shortfalls,
)

ALICE = UUID(int=1)
BOB = UUID(int=2)
_OWNERS = (ALICE, BOB)

_CHECKING = "Joint checking"


def _on(month: int, day: int, year: int = 2026) -> datetime.date:
    return datetime.date(year, month, day)


def _pair(alice: str, bob: str) -> tuple[OwnerAmount, ...]:
    return (OwnerAmount(ALICE, Decimal(alice)), OwnerAmount(BOB, Decimal(bob)))


def _point(year: int, month: int, alice: str, bob: str) -> ShareHistoryPoint:
    capitals = {ALICE: Decimal(alice), BOB: Decimal(bob)}
    return ShareHistoryPoint(year, month, share_percentages(capitals))


_MORTGAGE = LoanFigures(
    id=UUID(int=11),
    name="Mortgage",
    kind="amortizing",
    balance=Decimal("296620.00"),
    rate_percent=Decimal("6.0"),
    payment=Decimal("1798.65"),
    next_due=_on(11, 1),
    owner_parts=_pair("1050.41", "748.24"),
)
_SHORT_TERM_LOAN = LoanFigures(
    id=UUID(int=12),
    name="Short-term loan",
    kind="interest_only",
    balance=Decimal("40000.00"),
    rate_percent=Decimal("8.5"),
    payment=Decimal("283.33"),
    next_due=_on(10, 15),
    owner_parts=_pair("141.67", "141.66"),
)

_LOAN_BUCKET = bucket(
    "Loan payments", Decimal("2460.00"), Decimal("2460.00"), _on(9, 30)
)
_TAX_BUCKET = bucket("Property tax", Decimal("3620.00"), Decimal("3620.00"), _on(9, 30))
_BUCKETS = (
    _LOAN_BUCKET,
    _TAX_BUCKET,
    bucket("Renovation", Decimal("18500.00"), Decimal("18350.00"), _on(9, 28)),
    bucket("Repairs reserve", Decimal("2400.00")),
)
_TAX_BILL = Decimal("4860.00")


def _loan_payment(
    n: int, loan: LoanFigures, late_after: datetime.date
) -> ObligationFigures:
    return ObligationFigures(
        id=UUID(int=n),
        name=f"{loan.name} payment",
        kind="loan_payment",
        amount=loan.payment,
        is_estimate=False,
        due=loan.next_due,
        late_after=late_after,
        pays_from=_LOAN_BUCKET.name,
        shortfall=None,
    )


def _row(
    n: int,
    day: datetime.date,
    kind: ActivityKind,
    budget_line: str | None,
    amount: str,
    shares: tuple[OwnerAmount, ...],
) -> ActivityRow:
    return ActivityRow(
        id=UUID(int=n),
        date=day,
        account_name=_CHECKING,
        person_id=None,
        kind=kind,
        budget_line=budget_line,
        amount=Decimal(amount),
        shares=shares,
    )


def _deposit(n: int, day: datetime.date, person_id: UUID, amount: str) -> ActivityRow:
    """A deposit credits its depositor alone."""
    return ActivityRow(
        id=UUID(int=n),
        date=day,
        account_name=_CHECKING,
        person_id=person_id,
        kind="deposit",
        budget_line=None,
        amount=Decimal(amount),
        shares=tuple(
            OwnerAmount(owner, Decimal(amount) if owner == person_id else Decimal(0))
            for owner in _OWNERS
        ),
    )


EXAMPLE_HOUSE = HouseFigures(
    as_of=_on(10, 1),
    persons=(HousePerson(ALICE, "Alice"), HousePerson(BOB, "Bob")),
    put_in=put_in_section(
        _OWNERS,
        kinds={
            "closing": _pair("36000.00", "24000.00"),
            "loan-interest": _pair("11400.00", "8120.00"),
            "loan-principal": _pair("1970.00", "1410.00"),
            "property-tax": _pair("2840.00", "2020.00"),
            "insurance": _pair("1120.00", "800.00"),
            "repair": _pair("1940.00", "1380.00"),
            "agreed-work": _pair("3130.00", "3870.00"),
        },
        unspent_deposits=_pair("15760.00", "11220.00"),
    ),
    shares=shares_section((
        _point(2025, 10, "37120.00", "24800.00"),
        _point(2025, 11, "38330.00", "25690.00"),
        _point(2025, 12, "39540.00", "26580.00"),
        _point(2026, 1, "40750.00", "27470.00"),
        _point(2026, 2, "41960.00", "28360.00"),
        _point(2026, 3, "43170.00", "29250.00"),
        _point(2026, 4, "47220.00", "32160.00"),
        _point(2026, 5, "48430.00", "33050.00"),
        _point(2026, 6, "50600.00", "34980.00"),
        _point(2026, 7, "53980.00", "38820.00"),
        _point(2026, 8, "57190.00", "40710.00"),
        _point(2026, 9, "58400.00", "41600.00"),
    )),
    loans=(_MORTGAGE, _SHORT_TERM_LOAN),
    upcoming=with_shortfalls(
        (
            _loan_payment(21, _SHORT_TERM_LOAN, _on(10, 25)),
            _loan_payment(22, _MORTGAGE, _on(11, 16)),
            ObligationFigures(
                id=UUID(int=23),
                name="Property tax, first installment",
                kind="property_tax",
                amount=_TAX_BILL,
                is_estimate=True,
                due=_on(11, 1),
                late_after=_on(12, 10),
                pays_from=_TAX_BUCKET.name,
                shortfall=None,
            ),
        ),
        {b.name: b.balance for b in _BUCKETS},
    ),
    set_aside=set_aside_section(_BUCKETS),
    recent_activity=(
        _row(31, _on(10, 1), "payment", "mortgage", "-1798.65", _MORTGAGE.owner_parts),
        _row(
            32,
            _on(9, 30),
            "transfer",
            "property-tax",
            "-600.00",
            _pair("350.40", "249.60"),
        ),
        _row(33, _on(9, 28), "refund", "repair", "185.40", _pair("108.27", "77.13")),
        _deposit(34, _on(9, 25), ALICE, "1600.00"),
        _deposit(35, _on(9, 25), BOB, "1150.00"),
        _row(
            36,
            _on(9, 15),
            "payment",
            "short-term-loan",
            "-283.33",
            _SHORT_TERM_LOAN.owner_parts,
        ),
        _row(37, _on(9, 12), "payment", "repair", "-642.80", _pair("375.40", "267.40")),
        ActivityRow(
            id=UUID(int=38),
            date=_on(9, 8),
            account_name="Joint savings",
            person_id=None,
            kind="payment",
            budget_line="renovation",
            amount=Decimal("-3200.00"),
            shares=_pair("1868.80", "1331.20"),
        ),
        _row(39, _on(9, 1), "payment", "mortgage", "-1798.65", _MORTGAGE.owner_parts),
        _deposit(40, _on(8, 25), ALICE, "1600.00"),
    ),
)
