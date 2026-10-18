"""How the rows offered as a match are ranked: a settlement's transfer legs
(`src/domain/settlement_matching.py`) and an obligation's payment
(`src/domain/obligations.py`). Each scores its rows by its own weights."""

from collections.abc import Iterable
from typing import Final, Protocol

from src.domain.entities.transaction import Transaction

MAX_CANDIDATES: Final = 20


class ScoredRow(Protocol):
    """A row offered as a match, and how closely it matches."""

    @property
    def transaction(self) -> Transaction: ...
    @property
    def score(self) -> int: ...


def rank_and_limit[C: ScoredRow](scored: Iterable[C], limit: int) -> list[C]:
    """The candidates best score first, at most `limit`. A tie goes to the
    earlier row, then by id, so the order is stable."""
    ranked = sorted(
        scored, key=lambda c: (-c.score, c.transaction.date, c.transaction.id)
    )
    return ranked[:limit]
