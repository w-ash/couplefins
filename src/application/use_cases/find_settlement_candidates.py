from datetime import timedelta
from decimal import Decimal

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_decimal,
    positive_int,
)
from src.domain.date_math import month_bounds
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.domain.settlement_matching import (
    SettlementCandidate,
    find_settlement_candidates,
)

_DATE_PADDING = timedelta(days=7)


@define(frozen=True, slots=True)
class FindSettlementCandidatesCommand:
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)
    amount: Decimal = field(validator=positive_decimal)
    search_year: int | None = field(default=None)
    search_month: int | None = field(default=None)


@define(frozen=True, slots=True)
class FindSettlementCandidatesResult:
    candidates: list[SettlementCandidate]


@define(slots=True)
class FindSettlementCandidatesUseCase:
    async def execute(
        self, command: FindSettlementCandidatesCommand, uow: UnitOfWorkProtocol
    ) -> FindSettlementCandidatesResult:
        async with uow:
            sy = command.search_year or command.year
            sm = command.search_month or command.month
            start, end = month_bounds(sy, sm)
            search_start = start
            search_end = end + _DATE_PADDING

            transactions = await uow.transactions.get_by_date_range(
                search_start, search_end
            )
            merchants = await uow.settlement_merchants.get_all()

            candidates = find_settlement_candidates(
                transactions, command.amount, merchants
            )
            return FindSettlementCandidatesResult(candidates=candidates)
