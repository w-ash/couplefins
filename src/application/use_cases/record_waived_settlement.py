import uuid

from attrs import Factory, define, field

from src.application.use_cases._shared.command_validators import (
    optional_positive_int,
)
from src.application.use_cases._shared.date_math import month_bounds
from src.application.use_cases._shared.reconciliation_context import (
    ReconciliationContext,
    load_reconciliation_context,
)
from src.application.use_cases._shared.settlement_math import load_ledger
from src.application.use_cases._shared.settlement_records import (
    allocate_and_save_portions,
    build_settlement,
    validate_settlement_persons,
)
from src.application.use_cases._shared.upload_status import build_upload_statuses
from src.domain.entities.settlement import Settlement
from src.domain.exceptions import ValidationError
from src.domain.ledger import MonthKey, SettlementLedger
from src.domain.reconciliation import SettlementResult
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class RecordWaivedSettlementCommand:
    from_person_id: uuid.UUID
    to_person_id: uuid.UUID
    # Calendar year whose balance is waived. None waives every open month.
    waive_year: int | None = field(default=None, validator=optional_positive_int)
    notes: str = ""


@define(frozen=True, slots=True)
class RecordWaivedSettlementResult:
    settlement: Settlement
    warnings: list[str] = Factory(list[str])


async def _missing_upload_warnings(
    uow: UnitOfWorkProtocol,
    ctx: ReconciliationContext,
    open_months: list[MonthKey],
) -> list[str]:
    """Warn when the newest waived month lacks an upload — the waived
    amount may be premature."""
    if not open_months:
        return []
    start, end = month_bounds(*max(open_months))
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


def _waive_scope(
    ledger: SettlementLedger, waive_year: int | None
) -> tuple[SettlementResult | None, list[MonthKey]]:
    """(balance to waive, open months the waiver covers) for the scope."""
    open_months = [
        (m.year, m.month)
        for m in ledger.months
        if m.balance is not None and (waive_year is None or m.year == waive_year)
    ]
    if waive_year is None:
        return ledger.outstanding, open_months
    year_row = next((row for row in ledger.years if row.year == waive_year), None)
    return (year_row.balance if year_row else None), open_months


@define(slots=True)
class RecordWaivedSettlementUseCase:
    """Waive one calendar year's balance, or every open month.

    A waiver is a settlement whose portions cover the waived months —
    portions keep it inside its year regardless of when it is recorded. No
    period guard: Lock Month freezes transactions, and a waiver touches none.
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

            balance, open_months = _waive_scope(ledger, command.waive_year)
            if balance is None:
                scope = (
                    str(command.waive_year)
                    if command.waive_year is not None
                    else "Balance"
                )
                raise ValidationError(f"{scope} is already settled — nothing to waive")
            # A waiver recorded against the wrong direction would double the
            # balance instead of zeroing it (stale UI).
            if (command.from_person_id, command.to_person_id) != (
                balance.from_person_id,
                balance.to_person_id,
            ):
                raise ValidationError(
                    "Waive direction does not match the outstanding balance"
                )

            warnings = await _missing_upload_warnings(uow, ctx, open_months)

            settlement = build_settlement(
                from_person_id=command.from_person_id,
                to_person_id=command.to_person_id,
                amount=balance.amount,
                method=None,
                is_waived=True,
                notes=command.notes,
            )
            saved = await uow.settlements.save(settlement)
            await allocate_and_save_portions(uow, saved, ledger.months, open_months)
            await uow.commit()
            return RecordWaivedSettlementResult(settlement=saved, warnings=warnings)
