from decimal import ROUND_HALF_UP, Decimal

from src.domain.constants import SplitDefaults

_QUANTIZE_EXP = Decimal("0.01")
_HUNDRED = Decimal(100)


def check_payer_percentage(pct: int) -> None:
    """Raise ValueError if payer_percentage is outside 0-MAX_PAYER_PERCENTAGE."""
    if not (0 <= pct <= SplitDefaults.MAX_PAYER_PERCENTAGE):
        raise ValueError(
            f"payer_percentage must be 0-{SplitDefaults.MAX_PAYER_PERCENTAGE}, got {pct}"
        )


def compute_shares(amount: Decimal, payer_percentage: int) -> tuple[Decimal, Decimal]:
    """Return (payer_share, other_share) for a transaction amount and split."""
    abs_amount = abs(amount)
    payer_pct = Decimal(payer_percentage)
    payer_share = (abs_amount * payer_pct / _HUNDRED).quantize(
        _QUANTIZE_EXP, rounding=ROUND_HALF_UP
    )
    other_share = (abs_amount * (_HUNDRED - payer_pct) / _HUNDRED).quantize(
        _QUANTIZE_EXP, rounding=ROUND_HALF_UP
    )
    return payer_share, other_share
