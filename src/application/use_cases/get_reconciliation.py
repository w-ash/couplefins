from datetime import date, datetime

from attrs import define

from src.application.use_cases._shared.date_math import (
    detect_single_month,
    month_bounds,
)
from src.application.use_cases._shared.transactions import find_all_unmapped_categories
from src.application.use_cases._shared.upload_status import (
    UploadStatus,
    build_upload_statuses,
)
from src.domain.entities.person import Person
from src.domain.entities.transaction import Transaction
from src.domain.reconciliation import ReconciliationSummary, reconcile
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetReconciliationCommand:
    start_date: date
    end_date: date
    single_month: tuple[int, int] | None

    @classmethod
    def from_month(cls, year: int, month: int) -> GetReconciliationCommand:
        start, end = month_bounds(year, month)
        return cls(
            start_date=start,
            end_date=end,
            single_month=(year, month),
        )

    @classmethod
    def from_range(cls, start_date: date, end_date: date) -> GetReconciliationCommand:
        single = detect_single_month(start_date, end_date)
        return cls(start_date=start_date, end_date=end_date, single_month=single)


@define(frozen=True, slots=True)
class GetReconciliationResult:
    summary: ReconciliationSummary
    transactions: list[Transaction]
    upload_statuses: list[UploadStatus]
    unmapped_categories: list[str]
    persons: list[Person]
    is_finalized: bool | None
    finalized_at: datetime | None
    year: int | None
    month: int | None


@define(slots=True)
class GetReconciliationUseCase:
    async def execute(
        self, command: GetReconciliationCommand, uow: UnitOfWorkProtocol
    ) -> GetReconciliationResult:
        async with uow:
            persons = await uow.persons.get_all()
            transactions = await uow.transactions.get_shared_by_date_range(
                command.start_date, command.end_date
            )
            category_mappings = await uow.category_mappings.get_all()
            category_groups = await uow.category_groups.get_all()
            person_ids = [p.id for p in persons]
            uploads = (
                await uow.uploads.get_by_person_ids_with_transactions_in_date_range(
                    person_ids, command.start_date, command.end_date
                )
            )

            is_finalized: bool | None = None
            finalized_at: datetime | None = None
            if command.single_month:
                year, month = command.single_month
                period = await uow.reconciliation_periods.get_by_period(year, month)
                is_finalized = period.is_finalized if period else False
                finalized_at = period.finalized_at if period else None

            summary = reconcile(
                transactions,
                persons,
                category_mappings,
                category_groups,
                start_date=command.start_date,
                end_date=command.end_date,
            )

            upload_statuses = build_upload_statuses(persons, uploads)
            tx_categories = {tx.category for tx in transactions}
            unmapped = find_all_unmapped_categories(category_mappings, tx_categories)

            return GetReconciliationResult(
                summary=summary,
                transactions=transactions,
                upload_statuses=upload_statuses,
                unmapped_categories=unmapped,
                persons=persons,
                is_finalized=is_finalized,
                finalized_at=finalized_at,
                year=command.single_month[0] if command.single_month else None,
                month=command.single_month[1] if command.single_month else None,
            )
