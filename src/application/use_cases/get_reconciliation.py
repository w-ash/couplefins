from datetime import date, datetime

from attrs import define

from src.application.use_cases._shared.date_math import (
    detect_single_month,
    month_bounds,
)
from src.application.use_cases._shared.finalization import load_period_status
from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.application.use_cases._shared.transactions import (
    find_all_unmapped_categories,
    get_latest_transaction_month,
)
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
    latest_transaction_month: tuple[int, int] | None


@define(slots=True)
class GetReconciliationUseCase:
    async def execute(
        self, command: GetReconciliationCommand, uow: UnitOfWorkProtocol
    ) -> GetReconciliationResult:
        async with uow:
            ctx = await load_reconciliation_context(uow)
            transactions = await uow.transactions.get_household_by_date_range(
                command.start_date, command.end_date
            )
            uploads = (
                await uow.uploads.get_by_person_ids_with_transactions_in_date_range(
                    ctx.person_ids, command.start_date, command.end_date
                )
            )

            is_finalized: bool | None = None
            finalized_at: datetime | None = None
            if command.single_month:
                is_finalized, finalized_at = await load_period_status(
                    uow, *command.single_month
                )

            summary = reconcile(
                transactions,
                ctx.persons,
                ctx.categories,
                ctx.category_groups,
                start_date=command.start_date,
                end_date=command.end_date,
            )

            upload_statuses = build_upload_statuses(ctx.persons, uploads)
            tx_categories = {tx.category for tx in transactions}
            unmapped = find_all_unmapped_categories(ctx.categories, tx_categories)

            latest_month = await get_latest_transaction_month(uow)

            return GetReconciliationResult(
                summary=summary,
                transactions=transactions,
                upload_statuses=upload_statuses,
                unmapped_categories=unmapped,
                persons=ctx.persons,
                is_finalized=is_finalized,
                finalized_at=finalized_at,
                year=command.single_month[0] if command.single_month else None,
                month=command.single_month[1] if command.single_month else None,
                latest_transaction_month=latest_month,
            )
