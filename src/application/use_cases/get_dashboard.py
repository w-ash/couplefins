from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    optional_month_range,
    positive_int,
)
from src.application.use_cases._shared.date_math import month_bounds
from src.application.use_cases._shared.reconciliation_context import (
    ReconciliationContext,
    load_reconciliation_context,
)
from src.application.use_cases._shared.transactions import find_all_unmapped_categories
from src.application.use_cases._shared.upload_status import (
    UploadStatus,
    build_upload_statuses,
)
from src.domain.entities.person import Person
from src.domain.entities.transaction import Transaction
from src.domain.reconciliation import ReconciliationSummary, SettlementResult, reconcile
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetDashboardCommand:
    year: int = field(validator=positive_int)
    month: int | None = field(default=None, validator=optional_month_range)


@define(frozen=True, slots=True)
class MonthHistoryEntry:
    year: int
    month: int
    total_shared_spending: Decimal
    settlement_amount: Decimal
    settlement_from_person_id: UUID | None
    settlement_to_person_id: UUID | None
    is_finalized: bool


@define(frozen=True, slots=True)
class GetDashboardResult:
    current_month: ReconciliationSummary
    upload_statuses: list[UploadStatus]
    ytd_total_shared_spending: Decimal
    ytd_settlement: SettlementResult | None
    month_history: list[MonthHistoryEntry]
    persons: list[Person]
    unmapped_categories: list[str]
    is_finalized: bool
    finalized_at: datetime | None


def _partition_by_month(
    transactions: list[Transaction],
) -> dict[int, list[Transaction]]:
    by_month: dict[int, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        by_month[tx.date.month].append(tx)
    return by_month


def _reconcile_all_months(
    by_month: dict[int, list[Transaction]],
    ctx: ReconciliationContext,
    year: int,
) -> dict[int, ReconciliationSummary]:
    results: dict[int, ReconciliationSummary] = {}
    for month, txs in by_month.items():
        start, end = month_bounds(year, month)
        results[month] = reconcile(
            txs,
            ctx.persons,
            ctx.category_mappings,
            ctx.category_groups,
            start_date=start,
            end_date=end,
        )
    return results


def _build_month_history(
    summaries: dict[int, ReconciliationSummary],
    year: int,
    finalized_months: set[int],
) -> list[MonthHistoryEntry]:
    entries: list[MonthHistoryEntry] = []
    for month in sorted(summaries, reverse=True):
        settlement = summaries[month].settlement
        entries.append(
            MonthHistoryEntry(
                year=year,
                month=month,
                total_shared_spending=summaries[month].total_shared_spending,
                settlement_amount=settlement.amount if settlement else Decimal(0),
                settlement_from_person_id=settlement.from_person_id
                if settlement
                else None,
                settlement_to_person_id=settlement.to_person_id if settlement else None,
                is_finalized=month in finalized_months,
            )
        )
    return entries


def _resolve_active_month(
    by_month: dict[int, list[Transaction]],
    finalized_months: set[int],
    fallback_month: int,
) -> int:
    """Pick the most relevant month for the dashboard.

    Fallback chain: latest unfinalized month with transactions →
    latest month with transactions → current calendar month.
    """
    if not by_month:
        return fallback_month
    unfinalized = sorted(
        (m for m in by_month if m not in finalized_months), reverse=True
    )
    if unfinalized:
        return unfinalized[0]
    return max(by_month)


@define(slots=True)
class GetDashboardUseCase:
    async def execute(
        self, command: GetDashboardCommand, uow: UnitOfWorkProtocol
    ) -> GetDashboardResult:
        async with uow:
            ctx = await load_reconciliation_context(uow)

            all_year_txs = await uow.transactions.get_shared_by_year(command.year)
            by_month = _partition_by_month(all_year_txs)

            year_periods = await uow.reconciliation_periods.get_by_year(command.year)
            finalized_months = {p.month for p in year_periods if p.is_finalized}

            # Resolve active month: explicit param, or auto-detect
            now = datetime.now(tz=UTC)
            active_month = (
                command.month
                if command.month is not None
                else _resolve_active_month(by_month, finalized_months, now.month)
            )

            # Reconcile each month once, reuse for active month + history
            month_summaries = _reconcile_all_months(by_month, ctx, command.year)
            start, end = month_bounds(command.year, active_month)
            current_month = month_summaries.get(
                active_month,
                reconcile(
                    [],
                    ctx.persons,
                    ctx.category_mappings,
                    ctx.category_groups,
                    start_date=start,
                    end_date=end,
                ),
            )

            # YTD (Jan through active month)
            ytd_summary = reconcile(
                [tx for tx in all_year_txs if tx.date.month <= active_month],
                ctx.persons,
                ctx.category_mappings,
                ctx.category_groups,
                start_date=date(command.year, 1, 1),
                end_date=end,
            )

            uploads = await uow.uploads.get_by_person_ids_with_transactions_in_period(
                ctx.person_ids, command.year, active_month
            )

            current_period = next(
                (p for p in year_periods if p.month == active_month), None
            )

            tx_categories = {tx.category for tx in by_month.get(active_month, [])}

            return GetDashboardResult(
                current_month=current_month,
                upload_statuses=build_upload_statuses(ctx.persons, uploads),
                ytd_total_shared_spending=ytd_summary.total_shared_spending,
                ytd_settlement=ytd_summary.settlement,
                month_history=_build_month_history(
                    month_summaries, command.year, finalized_months
                ),
                persons=ctx.persons,
                unmapped_categories=find_all_unmapped_categories(
                    ctx.category_mappings, tx_categories
                ),
                is_finalized=current_period.is_finalized if current_period else False,
                finalized_at=current_period.finalized_at if current_period else None,
            )
