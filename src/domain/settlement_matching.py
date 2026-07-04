from decimal import Decimal

from attrs import define

from src.domain.entities.settlement_merchant import SettlementMerchant
from src.domain.entities.transaction import Transaction
from src.domain.filters import is_reconciliation_relevant

_SCORE_MERCHANT_MATCH = 3
_SCORE_AMOUNT_MATCH = 3
_SCORE_CATEGORY_MATCH = 2
_SCORE_PERSONAL = 1
_AMOUNT_TOLERANCE = Decimal("0.50")
_TRANSFER_KEYWORDS = {"transfer", "payment", "adjustment"}
_MAX_CANDIDATES = 20


@define(frozen=True, slots=True)
class SettlementCandidate:
    transaction: Transaction
    score: int
    match_reasons: tuple[str, ...]


def find_settlement_candidates(
    transactions: list[Transaction],
    settlement_amount: Decimal,
    merchants: list[SettlementMerchant],
) -> list[SettlementCandidate]:
    patterns = [(m.name, m.merchant_pattern.lower()) for m in merchants]
    candidates: list[SettlementCandidate] = []

    for tx in transactions:
        if not is_reconciliation_relevant(tx):
            continue

        score = 0
        reasons: list[str] = []

        merchant_lower = tx.merchant.lower()
        statement_lower = tx.original_statement.lower()
        for merchant_name, pattern in patterns:
            if pattern in merchant_lower or pattern in statement_lower:
                score += _SCORE_MERCHANT_MATCH
                reasons.append(f"Merchant matches {merchant_name}")
                break

        if any(kw in tx.category.lower() for kw in _TRANSFER_KEYWORDS):
            score += _SCORE_CATEGORY_MATCH
            reasons.append("Category suggests transfer")

        if abs(abs(tx.amount) - settlement_amount) <= _AMOUNT_TOLERANCE:
            score += _SCORE_AMOUNT_MATCH
            reasons.append("Amount matches settlement")

        # A real signal (merchant, category, or amount match) is required to
        # qualify — otherwise any non-household transaction would present as
        # a "matching transfer" with no actual evidence. `household` is a
        # ranking bonus among qualifying candidates, never a qualifier.
        if score == 0:
            continue

        if not tx.household:
            score += _SCORE_PERSONAL
            reasons.append("Personal transaction")

        candidates.append(
            SettlementCandidate(
                transaction=tx, score=score, match_reasons=tuple(reasons)
            )
        )

    candidates.sort(key=lambda c: (-c.score, c.transaction.date.isoformat()))
    return candidates[:_MAX_CANDIDATES]
