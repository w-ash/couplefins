import attrs
from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.domain.entities.reconciliation_period import ReconciliationPeriod
from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UnfinalizePeriodCommand:
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)


@define(frozen=True, slots=True)
class UnfinalizePeriodResult:
    period: ReconciliationPeriod


@define(slots=True)
class UnfinalizePeriodUseCase:
    async def execute(
        self, command: UnfinalizePeriodCommand, uow: UnitOfWorkProtocol
    ) -> UnfinalizePeriodResult:
        async with uow:
            existing = await uow.reconciliation_periods.get_by_period(
                command.year, command.month
            )

            if not existing or not existing.is_finalized:
                raise ValidationError(
                    f"Period {command.year}-{command.month:02d} is not finalized"
                )

            # Notes record what the couple agreed at close — clearing them
            # isn't necessary to unlock the period (is_finalized/finalized_at
            # already mark that) and would destroy that record.
            period = attrs.evolve(
                existing,
                is_finalized=False,
                finalized_at=None,
            )

            saved = await uow.reconciliation_periods.save(period)
            await uow.commit()
            return UnfinalizePeriodResult(period=saved)
