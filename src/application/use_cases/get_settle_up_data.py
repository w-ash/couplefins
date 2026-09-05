from datetime import UTC, datetime

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.application.use_cases._shared.finalization import load_period_status
from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.application.use_cases._shared.settlement_math import (
    LedgerSettlementRecord,
    load_month_audit_snapshot,
    load_settlement_ledger,
)
from src.application.use_cases._shared.transaction_reads import (
    fetch_latest_spending_month,
)
from src.application.use_cases._shared.transactions import (
    find_all_unmapped_categories,
)
from src.application.use_cases._shared.upload_status import UploadStatus
from src.domain.entities.category import Category
from src.domain.entities.person import Person
from src.domain.entities.transaction import Transaction
from src.domain.ledger import LedgerMonth, LedgerYear, year_row
from src.domain.reconciliation import (
    PayerGroupSummary,
    PayerSplitSummary,
    ReconciliationSummary,
    SettlementResult,
    compute_payer_group_summaries,
    compute_payer_split_summaries,
)
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetSettleUpDataCommand:
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)


@define(frozen=True, slots=True)
class GetSettleUpDataResult:
    """Every Settle Up number, precomputed — the UI renders, never derives.

    ``years``/``months`` carry the whole ledger; the client scopes them to
    its selected year by the ``year`` field, no arithmetic involved.
    """

    year: int
    month: int
    years: list[LedgerYear]  # ascending; every activity year + current
    months: list[LedgerMonth]  # chronological ascending, all years
    settlements: list[LedgerSettlementRecord]  # chronological ascending
    upload_statuses: list[UploadStatus]
    persons: list[Person]
    is_finalized: bool
    finalized_at: datetime | None
    transaction_count: int
    latest_transaction_month: tuple[int, int] | None
    finalization_warnings: list[str]
    payer_splits: list[PayerSplitSummary]
    payer_group_splits: list[PayerGroupSummary]


def _pad_years(years: list[LedgerYear], ensure: set[int]) -> list[LedgerYear]:
    """Engine years plus empty rows for years the page must offer anyway."""
    wanted = {row.year for row in years} | ensure
    return [year_row(years, year) for year in sorted(wanted)]


def _compute_audit_splits(
    summary: ReconciliationSummary,
    persons: list[Person],
) -> tuple[list[PayerSplitSummary], list[PayerGroupSummary]]:
    person_ids = [p.id for p in persons]
    return (
        compute_payer_split_summaries(summary.split_transactions, person_ids),
        compute_payer_group_summaries(
            summary.split_transactions, person_ids, summary.category_lookup
        ),
    )


def _build_finalization_warnings(
    is_finalized: bool,
    upload_statuses: list[UploadStatus],
    year: int,
    year_balance: SettlementResult | None,
    transactions: list[Transaction],
    categories: list[Category],
) -> list[str]:
    if is_finalized:
        return []
    warnings: list[str] = []
    warnings.extend(
        f"No upload from {us.person_name}"
        for us in upload_statuses
        if not us.has_uploaded
    )
    if year_balance is not None:
        warnings.append(f"Outstanding balance of ${year_balance.amount:,.2f} in {year}")
    tx_categories = {tx.category for tx in transactions}
    unmapped = find_all_unmapped_categories(categories, tx_categories)
    if unmapped:
        warnings.append(f"{len(unmapped)} unmapped categories")
    return warnings


@define(slots=True)
class GetSettleUpDataUseCase:
    async def execute(
        self, command: GetSettleUpDataCommand, uow: UnitOfWorkProtocol
    ) -> GetSettleUpDataResult:
        async with uow:
            ctx = await load_reconciliation_context(uow)

            bundle = await load_settlement_ledger(uow, ctx)
            snapshot = await load_month_audit_snapshot(
                uow, command.year, command.month, ctx, bundle.transactions
            )

            years = _pad_years(
                list(bundle.ledger.years),
                {command.year, datetime.now(UTC).year},
            )
            # _pad_years guarantees the selected year is present.
            selected_year = year_row(years, command.year)

            payer_splits, payer_group_splits = _compute_audit_splits(
                snapshot.summary, ctx.persons
            )

            is_finalized, finalized_at = await load_period_status(
                uow, command.year, command.month
            )

            # Scoped to the month's own year — locking a month answers for
            # that year's balance, not an all-time figure.
            warnings = _build_finalization_warnings(
                is_finalized,
                snapshot.upload_statuses,
                command.year,
                selected_year.balance,
                snapshot.transactions,
                ctx.categories,
            )

            return GetSettleUpDataResult(
                year=command.year,
                month=command.month,
                years=years,
                months=list(bundle.ledger.months),
                settlements=bundle.records,
                upload_statuses=snapshot.upload_statuses,
                persons=ctx.persons,
                is_finalized=is_finalized,
                finalized_at=finalized_at,
                transaction_count=snapshot.summary.transaction_count,
                latest_transaction_month=await fetch_latest_spending_month(uow, ctx),
                finalization_warnings=warnings,
                payer_splits=payer_splits,
                payer_group_splits=payer_group_splits,
            )
