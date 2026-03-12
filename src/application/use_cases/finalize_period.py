from datetime import UTC, datetime
import uuid

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
class FinalizePeriodCommand:
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)
    notes: str = ""


@define(frozen=True, slots=True)
class FinalizePeriodResult:
    period: ReconciliationPeriod


@define(slots=True)
class FinalizePeriodUseCase:
    async def execute(
        self, command: FinalizePeriodCommand, uow: UnitOfWorkProtocol
    ) -> FinalizePeriodResult:
        async with uow:
            existing = await uow.reconciliation_periods.get_by_period(
                command.year, command.month
            )

            if existing and existing.is_finalized:
                raise ValidationError(
                    f"Period {command.year}-{command.month:02d} is already finalized"
                )

            now = datetime.now(UTC)
            if existing:
                period = attrs.evolve(
                    existing,
                    is_finalized=True,
                    finalized_at=now,
                    notes=command.notes,
                )
            else:
                period = ReconciliationPeriod(
                    id=uuid.uuid4(),
                    year=command.year,
                    month=command.month,
                    is_finalized=True,
                    finalized_at=now,
                    notes=command.notes,
                    created_at=now,
                )

            saved = await uow.reconciliation_periods.save(period)
            await uow.commit()
            return FinalizePeriodResult(period=saved)
