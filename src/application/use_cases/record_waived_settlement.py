import uuid

from attrs import Factory, define, field

from src.application.use_cases._shared.command_validators import (
    assert_month_annotation_pair,
    optional_month_range,
    optional_positive_int,
)
from src.application.use_cases._shared.date_math import month_bounds
from src.application.use_cases._shared.reconciliation_context import (
    ReconciliationContext,
    load_reconciliation_context,
)
from src.application.use_cases._shared.settlement_math import load_ledger
from src.application.use_cases._shared.settlement_records import (
    build_settlement,
    validate_settlement_persons,
)
from src.application.use_cases._shared.upload_status import build_upload_statuses
from src.domain.entities.settlement import Settlement
from src.domain.exceptions import ValidationError
from src.domain.ledger import MonthKey
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class RecordWaivedSettlementCommand:
    from_person_id: uuid.UUID
    to_person_id: uuid.UUID
    # Optional "recorded against" annotation — display only, never math.
    year: int | None = field(default=None, validator=optional_positive_int)
    month: int | None = field(default=None, validator=optional_month_range)
    notes: str = ""

    def __attrs_post_init__(self) -> None:
        assert_month_annotation_pair(self.year, self.month)


@define(frozen=True, slots=True)
class RecordWaivedSettlementResult:
    settlement: Settlement
    warnings: list[str] = Factory(list[str])


async def _missing_upload_warnings(
    uow: UnitOfWorkProtocol,
    ctx: ReconciliationContext,
    span: tuple[MonthKey, MonthKey] | None,
) -> list[str]:
    """Warn when the outstanding span's newest month lacks an upload —
    the waived amount may be premature."""
    if span is None:
        return []
    start, end = month_bounds(*span[1])
    statuses = build_upload_statuses(
        ctx.persons,
        await uow.uploads.get_by_person_ids_with_transactions_in_date_range(
            ctx.person_ids, start, end
        ),
    )
    return [
        f"No upload from {us.person_name} yet — the waived amount may be premature"
        for us in statuses
        if not us.has_uploaded
    ]


@define(slots=True)
class RecordWaivedSettlementUseCase:
    """Waive the total outstanding balance across all months.

    No period guard: Lock Month freezes transactions, and a waiver touches
    none — it only records a payment-equivalent against the ledger.
    """

    async def execute(
        self, command: RecordWaivedSettlementCommand, uow: UnitOfWorkProtocol
    ) -> RecordWaivedSettlementResult:
        async with uow:
            await validate_settlement_persons(
                command.from_person_id, command.to_person_id, uow
            )

            ctx = await load_reconciliation_context(uow)
            ledger = (await load_ledger(uow, ctx)).ledger

            outstanding = ledger.outstanding
            if outstanding is None:
                raise ValidationError("Balance is already settled — nothing to waive")
            # A waiver recorded against the wrong direction would double the
            # outstanding balance instead of zeroing it (stale UI).
            if (command.from_person_id, command.to_person_id) != (
                outstanding.from_person_id,
                outstanding.to_person_id,
            ):
                raise ValidationError(
                    "Waive direction does not match the outstanding balance"
                )

            warnings = await _missing_upload_warnings(uow, ctx, ledger.span)

            settlement = build_settlement(
                year=command.year,
                month=command.month,
                from_person_id=command.from_person_id,
                to_person_id=command.to_person_id,
                amount=outstanding.amount,
                method=None,
                is_waived=True,
                notes=command.notes,
            )
            saved = await uow.settlements.save(settlement)
            await uow.commit()
            return RecordWaivedSettlementResult(settlement=saved, warnings=warnings)
