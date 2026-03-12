from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.application.use_cases._shared.transactions import find_all_unmapped_categories
from src.application.use_cases._shared.upload_status import (
    UploadStatus,
    build_upload_statuses,
)
from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.category_mapping import CategoryMapping
from src.domain.entities.person import Person
from src.domain.entities.transaction import Transaction
from src.domain.reconciliation import ReconciliationSummary, SettlementResult, reconcile
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetDashboardCommand:
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)


@define(frozen=True, slots=True)
class MonthHistoryEntry:
    year: int
    month: int
    total_shared_spending: Decimal
    settlement_amount: Decimal
    settlement_from_person_id: UUID | None
    settlement_to_person_id: UUID | None


@define(frozen=True, slots=True)
class GetDashboardResult:
    current_month: ReconciliationSummary
    upload_statuses: list[UploadStatus]
    ytd_total_shared_spending: Decimal
    ytd_settlement: SettlementResult | None
    month_history: list[MonthHistoryEntry]
    persons: list[Person]
    unmapped_categories: list[str]


def _partition_by_month(
    transactions: list[Transaction],
) -> dict[int, list[Transaction]]:
    by_month: dict[int, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        by_month[tx.date.month].append(tx)
    return by_month


def _reconcile_all_months(
    by_month: dict[int, list[Transaction]],
    persons: list[Person],
    category_mappings: list[CategoryMapping],
    category_groups: list[CategoryGroup],
    year: int,
) -> dict[int, ReconciliationSummary]:
    return {
        month: reconcile(
            txs, persons, category_mappings, category_groups, year=year, month=month
        )
        for month, txs in by_month.items()
    }


def _build_month_history(
    summaries: dict[int, ReconciliationSummary],
    year: int,
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
            )
        )
    return entries


@define(slots=True)
class GetDashboardUseCase:
    async def execute(
        self, command: GetDashboardCommand, uow: UnitOfWorkProtocol
    ) -> GetDashboardResult:
        async with uow:
            persons = await uow.persons.get_all()
            category_mappings = await uow.category_mappings.get_all()
            category_groups = await uow.category_groups.get_all()

            all_year_txs = await uow.transactions.get_shared_by_year(command.year)
            by_month = _partition_by_month(all_year_txs)

            # Reconcile each month once, reuse for current month + history
            month_summaries = _reconcile_all_months(
                by_month, persons, category_mappings, category_groups, command.year
            )
            current_month = month_summaries.get(
                command.month,
                reconcile(
                    [],
                    persons,
                    category_mappings,
                    category_groups,
                    year=command.year,
                    month=command.month,
                ),
            )

            # YTD (Jan through requested month)
            ytd_summary = reconcile(
                [tx for tx in all_year_txs if tx.date.month <= command.month],
                persons,
                category_mappings,
                category_groups,
                year=command.year,
                month=command.month,
            )

            uploads = await uow.uploads.get_by_person_ids_with_transactions_in_period(
                [p.id for p in persons], command.year, command.month
            )

            tx_categories = {tx.category for tx in by_month.get(command.month, [])}

            return GetDashboardResult(
                current_month=current_month,
                upload_statuses=build_upload_statuses(persons, uploads),
                ytd_total_shared_spending=ytd_summary.total_shared_spending,
                ytd_settlement=ytd_summary.settlement,
                month_history=_build_month_history(month_summaries, command.year),
                persons=persons,
                unmapped_categories=find_all_unmapped_categories(
                    category_mappings, tx_categories
                ),
            )
