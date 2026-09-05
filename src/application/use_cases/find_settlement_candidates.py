from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    optional_month_range,
    optional_positive_int,
    positive_decimal,
)
from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.application.use_cases._shared.settlement_math import load_ledger
from src.application.use_cases._shared.transaction_reads import fetch_listed_rows
from src.domain.date_math import month_bounds
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.domain.settlement_matching import (
    SettlementCandidate,
    find_settlement_candidates,
)

_DATE_PADDING = timedelta(days=7)


def _today() -> date:
    """Seam for tests — the default window clamp depends on the real clock."""
    return datetime.now(UTC).date()


@define(frozen=True, slots=True)
class FindSettlementCandidatesCommand:
    amount: Decimal = field(validator=positive_decimal)
    # Accepted for API compatibility; the search window comes from either the
    # explicit search month or the ledger's outstanding span.
    year: int | None = field(default=None, validator=optional_positive_int)
    month: int | None = field(default=None, validator=optional_month_range)
    search_year: int | None = field(default=None, validator=optional_positive_int)
    search_month: int | None = field(default=None, validator=optional_month_range)


@define(frozen=True, slots=True)
class FindSettlementCandidatesResult:
    candidates: list[SettlementCandidate]


@define(slots=True)
class FindSettlementCandidatesUseCase:
    async def execute(
        self, command: FindSettlementCandidatesCommand, uow: UnitOfWorkProtocol
    ) -> FindSettlementCandidatesResult:
        async with uow:
            window = await self._resolve_window(command, uow)
            if window is None:
                return FindSettlementCandidatesResult(candidates=[])
            start, end = window

            transactions = await fetch_listed_rows(uow, (start, end + _DATE_PADDING))
            merchants = await uow.settlement_merchants.get_all()

            candidates = find_settlement_candidates(
                transactions, command.amount, merchants
            )
            return FindSettlementCandidatesResult(candidates=candidates)

    @staticmethod
    async def _resolve_window(
        command: FindSettlementCandidatesCommand, uow: UnitOfWorkProtocol
    ) -> tuple[date, date] | None:
        """Explicit search month → that month; otherwise the outstanding span's
        start through today; nothing outstanding → None.

        The settling transfer is almost always dated in the current month —
        after the outstanding span it clears — so the default window must reach
        today, not stop at the span's newest open month, or the primary
        settle-up candidate never surfaces.
        """
        if command.search_year is not None and command.search_month is not None:
            return month_bounds(command.search_year, command.search_month)

        ctx = await load_reconciliation_context(uow)
        ledger = (await load_ledger(uow, ctx)).ledger
        span = ledger.span
        if span is None:
            return None
        start = date(span[0][0], span[0][1], 1)
        _, span_end = month_bounds(*span[1])
        return start, max(span_end, _today())
