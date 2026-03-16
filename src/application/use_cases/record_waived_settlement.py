from datetime import UTC, datetime
from decimal import Decimal
import uuid

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.application.use_cases._shared.settlement_records import (
    validate_settlement_persons,
)
from src.domain.entities.settlement import Settlement
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class RecordWaivedSettlementCommand:
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)
    from_person_id: uuid.UUID
    to_person_id: uuid.UUID
    notes: str = ""


@define(frozen=True, slots=True)
class RecordWaivedSettlementResult:
    settlement: Settlement


@define(slots=True)
class RecordWaivedSettlementUseCase:
    async def execute(
        self, command: RecordWaivedSettlementCommand, uow: UnitOfWorkProtocol
    ) -> RecordWaivedSettlementResult:
        async with uow:
            await validate_settlement_persons(
                command.from_person_id, command.to_person_id, uow
            )

            now = datetime.now(UTC)
            settlement = Settlement(
                id=uuid.uuid4(),
                year=command.year,
                month=command.month,
                amount=Decimal(0),
                from_person_id=command.from_person_id,
                to_person_id=command.to_person_id,
                method=None,
                is_waived=True,
                notes=command.notes,
                settled_at=now,
                created_at=now,
            )
            saved = await uow.settlements.save(settlement)
            await uow.commit()
            return RecordWaivedSettlementResult(settlement=saved)
