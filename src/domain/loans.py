"""Each loan's balance, from the servicer's statement and the payments since.

A payment row links to a loan by the label `loan:<slug>`, from any account.
Only money out counts as a payment. A loan's balance is its statement
balance less the principal part of each linked payment dated after the
statement date; a payment on or before that date is already in the
statement. Entering a new statement re-anchors the balance there.

- A row that also carries `share:loan-principal` is all principal, on
  either kind of loan: an extra principal payment pays no interest.
- Interest-only: any other payment is all interest.
- Amortizing: any other payment, in date order, pays the month's interest
  on the balance before it (balance x rate / 12, to the cent, half up) and
  the rest goes to principal.

Each owner's part of the scheduled payment follows their shares of the most
recent linked payment (`owner_shares`), or 50/50 before the first one. Like
settlement balances, these figures are computed from the rows on each read
and never stored.
"""

from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
import itertools
from uuid import UUID

from attrs import define

from src.domain.capital import share_kind
from src.domain.constants import LOAN_TAG_PREFIX, SplitDefaults
from src.domain.date_math import add_months
from src.domain.entities.loan import Loan
from src.domain.entities.obligation import Obligation
from src.domain.entities.transaction import Transaction
from src.domain.house import LoanFigures, OwnerAmount
from src.domain.splits import compute_shares, owner_shares

_CENT = Decimal("0.01")
_MONTHLY_RATE_DIVISOR = Decimal(100 * 12)


def loan_tag(loan: Loan) -> str:
    """The tag that links a payment row to the loan: `loan:<slug>`."""
    return f"{LOAN_TAG_PREFIX}{loan.slug}"


def linked_rows(loan: Loan, rows: Iterable[Transaction]) -> list[Transaction]:
    """The rows that carry the loan's tag, money in or out, at any date."""
    tag = loan_tag(loan)
    return [tx for tx in rows if tag in tx.tags]


def linked_payments(loan: Loan, rows: Iterable[Transaction]) -> list[Transaction]:
    """The money-out rows that carry the loan's tag, in date order. Rows of
    the same date order by id."""
    payments = [tx for tx in linked_rows(loan, rows) if tx.amount < 0]
    return sorted(payments, key=lambda tx: (tx.date, tx.id))


@define(frozen=True, slots=True)
class PaymentSplit:
    """One linked payment: its interest and principal parts, which sum to
    ``amount``, and the balance after it."""

    transaction_id: UUID
    date: date
    amount: Decimal
    interest: Decimal
    principal: Decimal
    balance_after: Decimal


def split_payment(loan: Loan, tx: Transaction, balance_before: Decimal) -> PaymentSplit:
    """Split one payment of the loan into interest and principal.

    A row that carries `share:loan-principal` is all principal. Otherwise an
    interest-only payment is all interest; an amortizing one pays the
    month's interest on the balance before it first, and the rest is
    principal, so a payment smaller than the interest is all interest. No
    interest accrues on a balance at or below zero.
    """
    amount = abs(tx.amount)
    if share_kind(tx) == "loan-principal":
        principal = amount
    elif loan.kind == "interest_only":
        principal = Decimal(0)
    else:
        accrued = (
            max(balance_before, Decimal(0)) * loan.annual_rate / _MONTHLY_RATE_DIVISOR
        ).quantize(_CENT, rounding=ROUND_HALF_UP)
        principal = max(amount - accrued, Decimal(0))
    return PaymentSplit(
        transaction_id=tx.id,
        date=tx.date,
        amount=amount,
        interest=amount - principal,
        principal=principal,
        balance_after=balance_before - principal,
    )


@define(frozen=True, slots=True)
class LoanBalance:
    """The loan's balance now, and the payments since the statement that
    moved it. ``balance`` is the statement balance less
    ``principal_paid``."""

    balance: Decimal
    principal_paid: Decimal
    interest_paid: Decimal
    payments: tuple[PaymentSplit, ...]


def compute_loan_balance(loan: Loan, rows: Iterable[Transaction]) -> LoanBalance:
    """The loan's balance from its statement and the linked payments dated
    after the statement date, in date order."""
    balance = loan.statement_balance
    splits: list[PaymentSplit] = []
    for tx in linked_payments(loan, rows):
        if tx.date <= loan.statement_balance_as_of:
            continue
        split = split_payment(loan, tx, balance)
        balance = split.balance_after
        splits.append(split)
    return LoanBalance(
        balance=balance,
        principal_paid=sum((s.principal for s in splits), Decimal(0)),
        interest_paid=sum((s.interest for s in splits), Decimal(0)),
        payments=tuple(splits),
    )


def owner_payment_parts(
    loan: Loan, rows: Iterable[Transaction], person_ids: Sequence[UUID]
) -> tuple[OwnerAmount, ...]:
    """Each owner's part of the loan's scheduled payment, in `person_ids`
    order, summing to it.

    The parts follow the owners' percentages of the most recent linked
    payment (`owner_shares`), and 50/50 before the first one. The first
    owner in `owner_shares` order rounds half up, as `share_amounts` does.
    Raise InvariantViolationError as `owner_shares` does.
    """
    payments = linked_payments(loan, rows)
    if payments:
        percentages = owner_shares(payments[-1], person_ids)
    else:
        percentages = dict.fromkeys(person_ids, SplitDefaults.DEFAULT_PAYER_PERCENTAGE)
    (lead, lead_pct), (other, _) = percentages.items()
    lead_amount, other_amount = compute_shares(loan.payment, lead_pct)
    parts = {lead: lead_amount, other: other_amount}
    return tuple(OwnerAmount(person, parts[person]) for person in person_ids)


def scheduled_due_dates(loan: Loan) -> Iterator[date]:
    """The loan's monthly due dates from its first, in order: through its
    term when it has one, else without end. Each falls on the first due
    date's day, or the month's last day when the month is shorter."""
    months = range(loan.term_months) if loan.term_months else itertools.count()
    return (add_months(loan.first_due_on, n) for n in months)


def open_due_dates(
    loan: Loan, obligations: Iterable[Obligation], on_or_after: date
) -> Iterator[date]:
    """The scheduled due dates from the first day of `on_or_after`'s month
    that no payment obligation of the loan covers yet: after the latest one,
    and in a month that has none. A payment due earlier in the month with no
    obligation yet is still open."""
    payments = [
        o for o in obligations if o.loan_id == loan.id and o.kind == "loan_payment"
    ]
    taken = {(o.due_on.year, o.due_on.month) for o in payments}
    latest = max((o.due_on for o in payments), default=None)
    month_start = on_or_after.replace(day=1)
    start = (
        month_start if latest is None else max(month_start, latest + timedelta(days=1))
    )
    return (
        day
        for day in scheduled_due_dates(loan)
        if day >= start and (day.year, day.month) not in taken
    )


def next_due_date(
    loan: Loan, obligations: Sequence[Obligation], as_of: date
) -> date | None:
    """When the loan's next payment is due; None once the loan is closed.

    The earliest unpaid payment obligation of the loan, late ones included.
    Without one, the first scheduled date from the first day of `as_of`'s
    month that no payment obligation covers (`open_due_dates`); None once
    the term has run out.
    """
    if not loan.is_open:
        return None
    unpaid = [
        o.due_on
        for o in obligations
        if o.loan_id == loan.id and o.kind == "loan_payment" and not o.is_paid
    ]
    if unpaid:
        return min(unpaid)
    return next(open_due_dates(loan, obligations, as_of), None)


def _figures(
    loan: Loan,
    rows: Sequence[Transaction],
    obligations: Sequence[Obligation],
    person_ids: Sequence[UUID],
    as_of: date,
) -> LoanFigures:
    return LoanFigures(
        id=loan.id,
        name=loan.name,
        lender=loan.lender,
        kind=loan.kind,
        principal=loan.principal,
        balance=compute_loan_balance(loan, rows).balance,
        rate_percent=loan.annual_rate,
        payment=loan.payment,
        statement_balance=loan.statement_balance,
        statement_balance_as_of=loan.statement_balance_as_of,
        next_due=next_due_date(loan, obligations, as_of),
        owner_parts=owner_payment_parts(loan, rows, person_ids),
        closed_on=loan.closed_on,
        replaced_by_loan_id=loan.replaced_by_loan_id,
    )


def loan_figures(
    loans: Iterable[Loan],
    rows: Iterable[Transaction],
    obligations: Iterable[Obligation],
    person_ids: Sequence[UUID],
    as_of: date,
) -> list[LoanFigures]:
    """Each loan, open or past, as the House page shows it on `as_of`, in
    `loans` order.

    The rows and the obligations are grouped by loan once, by the
    `loan:<slug>` tag and by `loan_id`, so each loan reads only its own.
    Raise InvariantViolationError as `owner_payment_parts` does.
    """
    rows_by_tag: defaultdict[str, list[Transaction]] = defaultdict(list)
    for tx in rows:
        for tag in dict.fromkeys(tx.tags):
            if tag.startswith(LOAN_TAG_PREFIX):
                rows_by_tag[tag].append(tx)
    by_loan: defaultdict[UUID, list[Obligation]] = defaultdict(list)
    for obligation in obligations:
        if obligation.loan_id is not None:
            by_loan[obligation.loan_id].append(obligation)
    return [
        _figures(loan, rows_by_tag[loan_tag(loan)], by_loan[loan.id], person_ids, as_of)
        for loan in loans
    ]
