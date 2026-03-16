from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    positive_int,
)
from src.application.use_cases._shared.settlement_records import (
    SettlementRecord,
    enrich_with_links,
)
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetSettlementsCommand:
    year: int = field(validator=positive_int)
    month: int | None = field(default=None)

    def __attrs_post_init__(self) -> None:
        if self.month is not None and not 1 <= self.month <= 12:  # noqa: PLR2004
            raise ValueError(f"month must be 1-12, got {self.month}")


@define(frozen=True, slots=True)
class GetSettlementsResult:
    settlements: list[SettlementRecord]


@define(slots=True)
class GetSettlementsUseCase:
    async def execute(
        self, command: GetSettlementsCommand, uow: UnitOfWorkProtocol
    ) -> GetSettlementsResult:
        async with uow:
            if command.month is not None:
                settlements = await uow.settlements.get_by_period(
                    command.year, command.month
                )
            else:
                settlements = await uow.settlements.get_by_year(command.year)

            records = await enrich_with_links(settlements, uow)
            return GetSettlementsResult(settlements=records)
