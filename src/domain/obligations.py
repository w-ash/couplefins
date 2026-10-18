"""What comes due on the co-owned home, and the rows that pay it.

An obligation is paid once a row is linked to it. Until then it is due, and
late after its delinquency date (its due date when it has none). Upcoming
lists the unpaid obligations in due order. Statuses are computed on each
read and never stored.
"""

from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from decimal import Decimal
import itertools
import uuid

from attrs import define

from src.domain.candidate_ranking import MAX_CANDIDATES, rank_and_limit
from src.domain.entities.loan import Loan
from src.domain.entities.obligation import Obligation, ObligationStatus
from src.domain.entities.transaction import Transaction
from src.domain.house import ObligationFigures
from src.domain.loans import loan_tag, open_due_dates

RECENT_PAID_LIMIT = 10
# The rows searched for an obligation's payment: from two weeks before its
# due date to about six weeks after.
_CANDIDATES_BEFORE = timedelta(days=14)
_CANDIDATES_AFTER = timedelta(days=45)
_CLOSE_AMOUNT = Decimal("1.00")
_CLOSE_AMOUNT_SHARE = Decimal("0.02")
_NEAR_DAYS = 7
_SAME_MONTH_DAYS = 30
_SCORE_AMOUNT = 3
_SCORE_NEAR = 2
_SCORE_SAME_MONTH = 1
_SCORE_LOAN_TAG = 2


def obligation_status(obligation: Obligation, today: date) -> ObligationStatus:
    """Paid once a row is linked; else late after the delinquency date (the
    due date when there is none), and due until then."""
    if obligation.is_paid:
        return "paid"
    if today > (obligation.late_after or obligation.due_on):
        return "late"
    return "due"


def upcoming(obligations: Iterable[Obligation]) -> list[Obligation]:
    """The unpaid obligations, late ones included, in due order. Those due
    the same day order by description, then id."""
    unpaid = [o for o in obligations if not o.is_paid]
    return sorted(unpaid, key=lambda o: (o.due_on, o.description, o.id))


def recently_paid(obligations: Iterable[Obligation]) -> list[Obligation]:
    """The newest paid obligations by due date, at most RECENT_PAID_LIMIT."""
    paid = [o for o in obligations if o.is_paid]
    paid.sort(key=lambda o: (o.due_on, o.id), reverse=True)
    return paid[:RECENT_PAID_LIMIT]


def obligation_figures(obligation: Obligation, today: date) -> ObligationFigures:
    """An obligation as the House page shows it on `today`, with no
    shortfall yet (`with_shortfalls` sets it)."""
    return ObligationFigures(
        id=obligation.id,
        name=obligation.description,
        kind=obligation.kind,
        status=obligation_status(obligation, today),
        amount=obligation.amount,
        is_estimate=obligation.is_estimate,
        due=obligation.due_on,
        late_after=obligation.late_after,
        pays_from=obligation.pays_from,
        loan_id=obligation.loan_id,
        paid_by_transaction_id=obligation.paid_by_transaction_id,
        shortfall=None,
    )


def generate_loan_payment_obligations(
    loan: Loan, existing: Sequence[Obligation], months: int, on_or_after: date
) -> list[Obligation]:
    """The loan's next `months` monthly payments as obligations.

    Each is due on a scheduled date of the loan (`scheduled_due_dates`)
    from the first day of `on_or_after`'s month, after the loan's latest
    payment obligation, in a month that has none (`open_due_dates`). Each
    is for the scheduled payment and names no pot. Fewer come back when the
    loan's term runs out first.
    """
    return [
        Obligation(
            id=uuid.uuid4(),
            asset_id=loan.asset_id,
            kind="loan_payment",
            description=f"{loan.name} payment",
            amount=loan.payment,
            due_on=day,
            loan_id=loan.id,
            paid_by_transaction_id=None,
        )
        for day in itertools.islice(open_due_dates(loan, existing, on_or_after), months)
    ]


def paid_by_others(
    obligation: Obligation, obligations: Iterable[Obligation]
) -> set[uuid.UUID]:
    """The rows that pay an obligation other than `obligation`. A row pays
    one obligation at most."""
    return {
        row_id
        for o in obligations
        if o.id != obligation.id and (row_id := o.paid_by_transaction_id) is not None
    }


def candidate_window(obligation: Obligation) -> tuple[date, date]:
    """The dates searched for the obligation's payment."""
    due = obligation.due_on
    return due - _CANDIDATES_BEFORE, due + _CANDIDATES_AFTER


@define(frozen=True, slots=True)
class PaymentCandidate:
    """A row that may pay an obligation, and how closely it matches.

    ``score`` adds 3 when the amount is within $1 or 2% of the
    obligation's; 2 when the row is dated within a week of the due date, or
    1 within 30 days; and 2 when the row carries the obligation's loan tag
    (`loan:<slug>`). The rows read run from 14 days before the due date to
    45 after, so a row 31 to 45 days out scores on its amount or tag alone.
    """

    transaction: Transaction
    score: int


def _score(obligation: Obligation, tx: Transaction, tag: str | None) -> int:
    difference = abs(abs(tx.amount) - obligation.amount)
    close = max(_CLOSE_AMOUNT, obligation.amount * _CLOSE_AMOUNT_SHARE)
    days = abs((tx.date - obligation.due_on).days)
    score = _SCORE_AMOUNT if difference <= close else 0
    if days <= _NEAR_DAYS:
        score += _SCORE_NEAR
    elif days <= _SAME_MONTH_DAYS:
        score += _SCORE_SAME_MONTH
    if tag is not None and tag in tx.tags:
        score += _SCORE_LOAN_TAG
    return score


def find_payment_candidates(
    obligation: Obligation,
    rows: Iterable[Transaction],
    *,
    obligations: Iterable[Obligation],
    loan: Loan | None,
) -> list[PaymentCandidate]:
    """The rows that may pay the obligation, best first.

    Only money out in `candidate_window` counts, only a row that scores,
    and no row that already pays another of `obligations`. `loan` is the
    obligation's loan, None when it has none. The best score comes first;
    a tie goes to the earlier row, then by id. At most MAX_CANDIDATES come
    back.
    """
    start, end = candidate_window(obligation)
    taken = paid_by_others(obligation, obligations)
    tag = loan_tag(loan) if loan is not None else None
    scored = (
        PaymentCandidate(tx, _score(obligation, tx, tag))
        for tx in rows
        if tx.amount < 0 and start <= tx.date <= end and tx.id not in taken
    )
    return rank_and_limit((c for c in scored if c.score > 0), MAX_CANDIDATES)
