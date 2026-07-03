from datetime import date, datetime
from uuid import UUID

from attrs import define, evolve

from src.application.use_cases._shared.command_validators import (
    Scope as ReconciliationScope,
)
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
from src.domain.reconciliation import (
    ReconciliationSummary,
    compute_gross_settlement,
    reconcile,
)
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetReconciliationCommand:
    start_date: date
    end_date: date
    single_month: tuple[int, int] | None
    scope: ReconciliationScope = "household"
    person_id: UUID | None = None
    tags: tuple[str, ...] | None = None

    @classmethod
    def from_month(
        cls,
        year: int,
        month: int,
        *,
        scope: ReconciliationScope = "household",
        person_id: UUID | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> GetReconciliationCommand:
        start, end = month_bounds(year, month)
        return cls(
            start_date=start,
            end_date=end,
            single_month=(year, month),
            scope=scope,
            person_id=person_id,
            tags=tags,
        )

    @classmethod
    def from_range(
        cls,
        start_date: date,
        end_date: date,
        *,
        scope: ReconciliationScope = "household",
        person_id: UUID | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> GetReconciliationCommand:
        single = detect_single_month(start_date, end_date)
        return cls(
            start_date=start_date,
            end_date=end_date,
            single_month=single,
            scope=scope,
            person_id=person_id,
            tags=tags,
        )


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
            transactions = await self._fetch_transactions(command, uow)
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

            # The settlement figure is computed over ALL settlement-relevant
            # rows, not the scoped display set above — both partners and every
            # scope see the same number, matching the Settle Up page.
            # summary.split_transactions still describes the display set.
            settlement_txs = (
                await uow.transactions.get_settlement_relevant_by_date_range(
                    command.start_date, command.end_date, tags=command.tags
                )
            )
            summary = evolve(
                summary,
                settlement=compute_gross_settlement(settlement_txs, ctx.person_ids),
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

    @staticmethod
    async def _fetch_transactions(
        command: GetReconciliationCommand, uow: UnitOfWorkProtocol
    ) -> list[Transaction]:
        tags = command.tags

        if command.scope == "personal" and command.person_id is not None:
            txs = await uow.transactions.get_by_person_and_date_range(
                command.person_id, command.start_date, command.end_date, tags=tags
            )
            return [tx for tx in txs if not tx.household]

        if command.scope == "all" and command.person_id is not None:
            household_txs = await uow.transactions.get_household_by_date_range(
                command.start_date, command.end_date, tags=tags
            )
            person_txs = await uow.transactions.get_by_person_and_date_range(
                command.person_id, command.start_date, command.end_date, tags=tags
            )
            household_ids = {tx.id for tx in household_txs}
            personal_non_household = [
                tx
                for tx in person_txs
                if not tx.household and tx.id not in household_ids
            ]
            return household_txs + personal_non_household

        return await uow.transactions.get_household_by_date_range(
            command.start_date, command.end_date, tags=tags
        )
