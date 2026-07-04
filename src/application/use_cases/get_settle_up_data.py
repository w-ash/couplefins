from datetime import datetime
from decimal import Decimal

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
from src.application.use_cases._shared.settlement_records import SettlementRecord
from src.application.use_cases._shared.transactions import (
    find_all_unmapped_categories,
    get_latest_transaction_month,
)
from src.application.use_cases._shared.upload_status import UploadStatus
from src.domain.entities.category import Category
from src.domain.entities.person import Person
from src.domain.entities.transaction import Transaction
from src.domain.ledger import LedgerMonth, MonthKey, month_remaining_result
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
    year: int
    month: int
    owed: SettlementResult | None
    net_position: SettlementResult | None
    recorded_settlements: list[SettlementRecord]
    remaining_balance: Decimal
    outstanding: SettlementResult | None
    outstanding_span: tuple[MonthKey, MonthKey] | None
    ledger_months: list[LedgerMonth]
    all_settlements: list[LedgerSettlementRecord]
    upload_statuses: list[UploadStatus]
    persons: list[Person]
    is_finalized: bool
    finalized_at: datetime | None
    transaction_count: int
    latest_transaction_month: tuple[int, int] | None
    finalization_warnings: list[str]
    payer_splits: list[PayerSplitSummary]
    payer_group_splits: list[PayerGroupSummary]


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
    outstanding: SettlementResult | None,
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
    if outstanding is not None:
        warnings.append(
            f"Outstanding balance of ${outstanding.amount:.2f} across all months"
        )
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
                uow, command.year, command.month, ctx
            )

            # The selected month's ledger position — its gross minus what
            # FIFO applied to it — not month-annotation netting.
            month_row = next(
                (
                    m
                    for m in bundle.ledger.months
                    if (m.year, m.month) == (command.year, command.month)
                ),
                None,
            )
            net_position = (
                month_remaining_result(month_row) if month_row is not None else None
            )

            payer_splits, payer_group_splits = _compute_audit_splits(
                snapshot.summary, ctx.persons
            )

            is_finalized, finalized_at = await load_period_status(
                uow, command.year, command.month
            )

            warnings = _build_finalization_warnings(
                is_finalized,
                snapshot.upload_statuses,
                bundle.ledger.outstanding,
                snapshot.transactions,
                ctx.categories,
            )

            return GetSettleUpDataResult(
                year=command.year,
                month=command.month,
                owed=snapshot.summary.settlement,
                net_position=net_position,
                recorded_settlements=snapshot.records,
                remaining_balance=(net_position.amount if net_position else Decimal(0)),
                outstanding=bundle.ledger.outstanding,
                outstanding_span=bundle.ledger.span,
                ledger_months=list(bundle.ledger.months),
                all_settlements=bundle.records,
                upload_statuses=snapshot.upload_statuses,
                persons=ctx.persons,
                is_finalized=is_finalized,
                finalized_at=finalized_at,
                transaction_count=snapshot.summary.transaction_count,
                latest_transaction_month=await get_latest_transaction_month(uow),
                finalization_warnings=warnings,
                payer_splits=payer_splits,
                payer_group_splits=payer_group_splits,
            )
