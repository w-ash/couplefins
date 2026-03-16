from datetime import datetime
from decimal import Decimal

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.application.use_cases._shared.date_math import month_bounds
from src.application.use_cases._shared.settlement_records import (
    SettlementRecord,
    enrich_with_links,
)
from src.application.use_cases._shared.upload_status import (
    UploadStatus,
    build_upload_statuses,
)
from src.domain.entities.person import Person
from src.domain.reconciliation import SettlementResult, reconcile
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetSettleUpDataCommand:
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)


@define(frozen=True, slots=True)
class GetSettleUpDataResult:
    year: int
    month: int
    owed: SettlementResult | None
    recorded_settlements: list[SettlementRecord]
    remaining_balance: Decimal
    upload_statuses: list[UploadStatus]
    persons: list[Person]
    is_finalized: bool
    finalized_at: datetime | None


@define(slots=True)
class GetSettleUpDataUseCase:
    async def execute(  # noqa: PLR0914
        self, command: GetSettleUpDataCommand, uow: UnitOfWorkProtocol
    ) -> GetSettleUpDataResult:
        async with uow:
            persons = await uow.persons.get_all()
            person_ids = [p.id for p in persons]

            start, end = month_bounds(command.year, command.month)
            transactions = await uow.transactions.get_shared_by_date_range(start, end)
            category_mappings = await uow.category_mappings.get_all()
            category_groups = await uow.category_groups.get_all()

            summary = reconcile(
                transactions,
                persons,
                category_mappings,
                category_groups,
                start_date=start,
                end_date=end,
            )

            settlements = await uow.settlements.get_by_period(
                command.year, command.month
            )
            records = await enrich_with_links(settlements, uow)

            total_settled = sum((r.settlement.amount for r in records), Decimal(0))
            owed_amount = (
                summary.settlement.amount if summary.settlement else Decimal(0)
            )
            remaining = max(Decimal(0), owed_amount - total_settled)

            uploads = (
                await uow.uploads.get_by_person_ids_with_transactions_in_date_range(
                    person_ids, start, end
                )
            )
            upload_statuses = build_upload_statuses(persons, uploads)

            period = await uow.reconciliation_periods.get_by_period(
                command.year, command.month
            )
            is_finalized = period.is_finalized if period else False
            finalized_at = period.finalized_at if period else None

            return GetSettleUpDataResult(
                year=command.year,
                month=command.month,
                owed=summary.settlement,
                recorded_settlements=records,
                remaining_balance=remaining,
                upload_statuses=upload_statuses,
                persons=persons,
                is_finalized=is_finalized,
                finalized_at=finalized_at,
            )
