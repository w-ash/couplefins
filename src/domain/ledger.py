"""Settlement ledger — explicit per-month portions (v1.11.0).

Every settlement records exactly which months it covers and with how much:
portions of (year, month, amount) summing to the settlement amount. They
are allocated once, at record time (see ``plan_portions``); display math
only ever adds them up:

- Month balance = net of its charges' shares - portions applied to it.
- Year = sum of its months. Outstanding = sum of all months.

A month paid past its charges simply shows its balance in the other
direction — the normal state (a month settled in full routinely swings).

All computation happens in a signed space anchored to the UUID-sorted person
pair: positive means "person A (lower UUID) owes person B".
"""

from collections.abc import Iterable, Sequence
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from attrs import define, field

from src.domain.constants import CoupleDefaults
from src.domain.entities.settlement import Settlement
from src.domain.entities.settlement_portion import SettlementPortion
from src.domain.entities.transaction import Transaction
from src.domain.filters import is_split_relevant
from src.domain.month_key import MonthKey
from src.domain.reconciliation import SettlementResult
from src.domain.splits import compute_shares

_ZERO = Decimal(0)


class MonthSettlementStatus(StrEnum):
    SETTLED = "settled"
    PARTIALLY_SETTLED = "partially_settled"
    CARRIED_FORWARD = "carried_forward"


@define(frozen=True, slots=True)
class PortionPlan:
    """One planned (month, amount) slice of a settlement payment."""

    year: int
    month: int
    amount: Decimal


@define(frozen=True, slots=True)
class LedgerSettlement:
    """One settlement's stored portions, resolved for display."""

    settlement_id: UUID
    portions: tuple[PortionPlan, ...]  # ascending by month


@define(frozen=True, slots=True)
class LedgerMonth:
    """One month's balances, all direction-resolved (None means zero)."""

    year: int
    month: int
    charged: SettlementResult | None  # net of the month's charges' shares
    paid: SettlementResult | None  # net portions applied to this month
    balance: SettlementResult | None  # charged - paid
    status: MonthSettlementStatus
    # True when the balance direction differs from its year's — the UI names
    # the person only on such rows.
    runs_against_year: bool


@define(frozen=True, slots=True)
class LedgerYear:
    """One calendar year's totals — the sum of its months."""

    year: int
    charged: SettlementResult | None
    paid: SettlementResult | None
    balance: SettlementResult | None
    span: tuple[MonthKey, MonthKey] | None  # (oldest, newest) charged month


@define(frozen=True, slots=True)
class SettlementLedger:
    outstanding: SettlementResult | None  # sum of all month balances
    span: tuple[MonthKey, MonthKey] | None  # (oldest, newest) open month
    months: tuple[LedgerMonth, ...]  # chronological ascending
    years: tuple[LedgerYear, ...]  # ascending
    settlements: tuple[LedgerSettlement, ...]  # chronological by settled_at


def empty_ledger_year(year: int) -> LedgerYear:
    """A year with no activity — for padding the current calendar year in."""
    return LedgerYear(year=year, charged=None, paid=None, balance=None, span=None)


def year_row(years: Iterable[LedgerYear], year: int) -> LedgerYear:
    """One calendar year's totals, or an empty row when it has no activity."""
    return next((row for row in years if row.year == year), empty_ledger_year(year))


def sum_settlement_results(
    results: Iterable[SettlementResult | None],
    person_ids: list[UUID],
) -> SettlementResult | None:
    """Direction-aware sum of positions over the UUID-anchored person pair.

    None when the signed total nets to zero (or the couple is incomplete).
    """
    if len(person_ids) != CoupleDefaults.EXPECTED_PERSON_COUNT:
        return None
    person_a, person_b = sorted(person_ids)
    signed = sum((_signed_result(result, person_a) for result in results), _ZERO)
    return _result_from_signed(signed, person_a, person_b)


def plan_portions(
    months: Iterable[LedgerMonth],
    amount: Decimal,
    from_person_id: UUID,
    covered_months: Sequence[MonthKey],
) -> tuple[PortionPlan, ...]:
    """Split a payment across its covered months, at record time.

    Clears each covered month's balance oldest first (only months where the
    payer is the one owing); the remainder lands on the newest covered
    month, swinging it if need be. The portions sum to ``amount`` exactly.
    """
    if not covered_months or amount <= _ZERO:
        return ()
    balance_by_key = {(m.year, m.month): m.balance for m in months}
    covered = sorted(set(covered_months))
    remaining = amount
    portions: dict[MonthKey, Decimal] = {}
    for key in covered:
        if remaining == _ZERO:
            break
        balance = balance_by_key.get(key)
        if balance is None or balance.from_person_id != from_person_id:
            continue
        take = min(remaining, balance.amount)
        portions[key] = take
        remaining -= take
    if remaining > _ZERO:
        newest = covered[-1]
        portions[newest] = portions.get(newest, _ZERO) + remaining
    return tuple(
        PortionPlan(year=year, month=month, amount=portions[year, month])
        for year, month in sorted(portions)
    )


def compute_ledger(
    transactions: list[Transaction],
    settlements: Sequence[Settlement],
    portions: Sequence[SettlementPortion],
    person_ids: list[UUID],
) -> SettlementLedger:
    """Compute the settlement ledger over all-time data.

    Caller passes settlement-relevant transactions (any date range), all
    settlements, and all stored portions. Requires exactly two person ids;
    anything else yields an empty ledger.
    """
    if len(person_ids) != CoupleDefaults.EXPECTED_PERSON_COUNT:
        return _empty_ledger()
    person_a, person_b = sorted(person_ids)

    charged: dict[MonthKey, Decimal] = {}
    for tx in transactions:
        key = (tx.date.year, tx.date.month)
        charged[key] = charged.get(key, _ZERO) + _signed_share(tx, person_a)

    ordered = sorted(settlements, key=lambda s: (s.settled_at, s.created_at, s.id))
    portions_by_settlement: dict[UUID, list[SettlementPortion]] = {}
    for portion in portions:
        portions_by_settlement.setdefault(portion.settlement_id, []).append(portion)

    books = _Books(person_a=person_a, person_b=person_b, charged=charged)
    ledger_settlements: list[LedgerSettlement] = []
    for settlement in ordered:
        resolved = _resolved_portions(settlement, portions_by_settlement)
        books.apply(settlement, resolved)
        ledger_settlements.append(
            LedgerSettlement(settlement_id=settlement.id, portions=resolved)
        )

    keys = books.month_keys()
    open_keys = [key for key in keys if books.balance(key) != _ZERO]
    return SettlementLedger(
        outstanding=books.result(sum((books.balance(k) for k in keys), _ZERO)),
        span=(min(open_keys), max(open_keys)) if open_keys else None,
        months=books.build_months(keys),
        years=books.build_years(keys),
        settlements=tuple(ledger_settlements),
    )


def _empty_ledger() -> SettlementLedger:
    return SettlementLedger(
        outstanding=None, span=None, months=(), years=(), settlements=()
    )


def _signed_share(tx: Transaction, person_a: UUID) -> Decimal:
    """The counterparty's share of one charge, signed (+ = A owes B).

    Linear per transaction: summing these over a month reproduces
    ``compute_gross_settlement`` for that month exactly.
    """
    if not is_split_relevant(tx):
        return _ZERO
    _, other_share = compute_shares(tx.amount, tx.payer_percentage)
    # Expense: the other person owes the payer. Refund: the reverse.
    owed_to_payer = other_share if tx.amount < 0 else -other_share
    return -owed_to_payer if tx.payer_person_id == person_a else owed_to_payer


def _signed_result(result: SettlementResult | None, person_a: UUID) -> Decimal:
    if result is None or result.amount == _ZERO:
        return _ZERO
    return result.amount if result.from_person_id == person_a else -result.amount


def _resolved_portions(
    settlement: Settlement,
    portions_by_settlement: dict[UUID, list[SettlementPortion]],
) -> tuple[PortionPlan, ...]:
    """Stored portions, ascending; a portion-less settlement (pre-migration
    data, defensive) covers its settled_at month in full."""
    stored = portions_by_settlement.get(settlement.id)
    if not stored:
        if settlement.amount == _ZERO:
            return ()
        return (
            PortionPlan(
                year=settlement.settled_at.year,
                month=settlement.settled_at.month,
                amount=settlement.amount,
            ),
        )
    return tuple(
        PortionPlan(year=p.year, month=p.month, amount=p.amount)
        for p in sorted(stored, key=lambda p: (p.year, p.month))
    )


@define(slots=True)
class _Books:
    """Signed per-month running totals while portions apply."""

    person_a: UUID
    person_b: UUID
    charged: dict[MonthKey, Decimal]
    paid: dict[MonthKey, Decimal] = field(factory=dict)

    def apply(self, settlement: Settlement, resolved: tuple[PortionPlan, ...]) -> None:
        sign = 1 if settlement.from_person_id == self.person_a else -1
        for plan in resolved:
            key = (plan.year, plan.month)
            self.paid[key] = self.paid.get(key, _ZERO) + sign * plan.amount

    def month_keys(self) -> list[MonthKey]:
        return sorted(set(self.charged) | set(self.paid))

    def balance(self, key: MonthKey) -> Decimal:
        return self.charged.get(key, _ZERO) - self.paid.get(key, _ZERO)

    def result(self, signed: Decimal) -> SettlementResult | None:
        return _result_from_signed(signed, self.person_a, self.person_b)

    def build_months(self, keys: list[MonthKey]) -> tuple[LedgerMonth, ...]:
        year_signed: dict[int, Decimal] = {}
        for key in keys:
            year_signed[key[0]] = year_signed.get(key[0], _ZERO) + self.balance(key)
        return tuple(self._build_month(key, year_signed[key[0]]) for key in keys)

    def _build_month(self, key: MonthKey, year_balance: Decimal) -> LedgerMonth:
        paid_signed = self.paid.get(key, _ZERO)
        balance_signed = self.balance(key)
        if balance_signed == _ZERO:
            status = MonthSettlementStatus.SETTLED
        elif paid_signed == _ZERO:
            status = MonthSettlementStatus.CARRIED_FORWARD
        else:
            status = MonthSettlementStatus.PARTIALLY_SETTLED
        return LedgerMonth(
            year=key[0],
            month=key[1],
            charged=self.result(self.charged.get(key, _ZERO)),
            paid=self.result(paid_signed),
            balance=self.result(balance_signed),
            status=status,
            runs_against_year=(
                balance_signed != _ZERO
                and (
                    year_balance == _ZERO
                    or (balance_signed > _ZERO) != (year_balance > _ZERO)
                )
            ),
        )

    def build_years(self, keys: list[MonthKey]) -> tuple[LedgerYear, ...]:
        rows: list[LedgerYear] = []
        for year in sorted({key[0] for key in keys}):
            year_keys = [key for key in keys if key[0] == year]
            charged_keys = [k for k in year_keys if self.charged.get(k, _ZERO) != _ZERO]
            rows.append(
                LedgerYear(
                    year=year,
                    charged=self.result(
                        sum((self.charged.get(k, _ZERO) for k in year_keys), _ZERO)
                    ),
                    paid=self.result(
                        sum((self.paid.get(k, _ZERO) for k in year_keys), _ZERO)
                    ),
                    balance=self.result(
                        sum((self.balance(k) for k in year_keys), _ZERO)
                    ),
                    span=(
                        (min(charged_keys), max(charged_keys)) if charged_keys else None
                    ),
                )
            )
        return tuple(rows)


def _result_from_signed(
    signed: Decimal, person_a: UUID, person_b: UUID
) -> SettlementResult | None:
    if signed == _ZERO:
        return None
    if signed > _ZERO:
        return SettlementResult(
            amount=signed, from_person_id=person_a, to_person_id=person_b
        )
    return SettlementResult(
        amount=-signed, from_person_id=person_b, to_person_id=person_a
    )
