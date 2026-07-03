from decimal import Decimal
import uuid

from attrs import Factory, define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.application.use_cases._shared.settlement_math import (
    load_month_settlement_snapshot,
)
from src.application.use_cases._shared.settlement_records import (
    build_settlement,
    validate_settlement_persons,
)
from src.domain.entities.settlement import Settlement
from src.domain.exceptions import ValidationError
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
    warnings: list[str] = Factory(list[str])


@define(slots=True)
class RecordWaivedSettlementUseCase:
    async def execute(
        self, command: RecordWaivedSettlementCommand, uow: UnitOfWorkProtocol
    ) -> RecordWaivedSettlementResult:
        async with uow:
            await validate_settlement_persons(
                command.from_person_id, command.to_person_id, uow
            )

            ctx = await load_reconciliation_context(uow)
            snapshot = await load_month_settlement_snapshot(
                uow, command.year, command.month, ctx
            )

            net = snapshot.net_position
            # A balanced month yields a zero-amount result rather than None.
            if net is None or net.amount == Decimal(0):
                raise ValidationError("Balance is already settled — nothing to waive")
            # A waiver recorded against the wrong direction would double the
            # balance in compute_net_position instead of zeroing it.
            if (command.from_person_id, command.to_person_id) != (
                net.from_person_id,
                net.to_person_id,
            ):
                raise ValidationError(
                    "Waive direction does not match the outstanding balance"
                )

            warnings = [
                f"No upload from {us.person_name} yet — "
                "the waived amount may be premature"
                for us in snapshot.upload_statuses
                if not us.has_uploaded
            ]

            settlement = build_settlement(
                year=command.year,
                month=command.month,
                from_person_id=command.from_person_id,
                to_person_id=command.to_person_id,
                amount=net.amount,
                method=None,
                is_waived=True,
                notes=command.notes,
            )
            saved = await uow.settlements.save(settlement)
            await uow.commit()
            return RecordWaivedSettlementResult(settlement=saved, warnings=warnings)
