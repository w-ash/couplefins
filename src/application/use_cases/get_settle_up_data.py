from datetime import datetime
from decimal import Decimal

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.application.use_cases._shared.date_math import month_bounds
from src.application.use_cases._shared.finalization import load_period_status
from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.application.use_cases._shared.settlement_records import (
    SettlementRecord,
    enrich_with_links,
)
from src.application.use_cases._shared.transactions import (
    find_all_unmapped_categories,
    get_latest_transaction_month,
)
from src.application.use_cases._shared.upload_status import (
    UploadStatus,
    build_upload_statuses,
)
from src.domain.categories import build_category_lookup
from src.domain.entities.category import Category
from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.person import Person
from src.domain.entities.transaction import Transaction
from src.domain.reconciliation import (
    PayerGroupSummary,
    PayerSplitSummary,
    SettlementResult,
    compute_net_position,
    compute_payer_group_summaries,
    compute_payer_split_summaries,
    reconcile,
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
    upload_statuses: list[UploadStatus]
    persons: list[Person]
    is_finalized: bool
    finalized_at: datetime | None
    transaction_count: int
    latest_transaction_month: tuple[int, int] | None
    finalization_warnings: list[str]
    payer_splits: list[PayerSplitSummary]
    payer_group_splits: list[PayerGroupSummary]


@define(frozen=True, slots=True)
class _AuditSummaries:
    payer_splits: list[PayerSplitSummary]
    payer_group_splits: list[PayerGroupSummary]


def _build_audit_summaries(
    split_transactions: list[Transaction],
    persons: list[Person],
    categories: list[Category],
    category_groups: list[CategoryGroup],
) -> _AuditSummaries:
    person_ids = [p.id for p in persons]
    lookup = build_category_lookup(categories, category_groups)
    return _AuditSummaries(
        payer_splits=compute_payer_split_summaries(split_transactions, person_ids),
        payer_group_splits=compute_payer_group_summaries(
            split_transactions, person_ids, lookup
        ),
    )


def _build_finalization_warnings(
    is_finalized: bool,
    upload_statuses: list[UploadStatus],
    remaining: Decimal,
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
    if remaining > 0:
        warnings.append(f"Unsettled balance of ${remaining:.2f}")
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

            start, end = month_bounds(command.year, command.month)
            transactions = await uow.transactions.get_household_by_date_range(
                start, end
            )

            summary = reconcile(
                transactions,
                ctx.persons,
                ctx.categories,
                ctx.category_groups,
                start_date=start,
                end_date=end,
            )

            audit = _build_audit_summaries(
                summary.split_transactions,
                ctx.persons,
                ctx.categories,
                ctx.category_groups,
            )

            settlements = await uow.settlements.get_by_period(
                command.year, command.month
            )
            records = await enrich_with_links(settlements, uow)

            net_pos = compute_net_position(
                summary.settlement,
                [r.settlement for r in records],
            )
            remaining = net_pos.amount if net_pos else Decimal(0)

            uploads = (
                await uow.uploads.get_by_person_ids_with_transactions_in_date_range(
                    ctx.person_ids, start, end
                )
            )
            upload_statuses = build_upload_statuses(ctx.persons, uploads)

            is_finalized, finalized_at = await load_period_status(
                uow, command.year, command.month
            )

            warnings = _build_finalization_warnings(
                is_finalized, upload_statuses, remaining, transactions, ctx.categories
            )

            return GetSettleUpDataResult(
                year=command.year,
                month=command.month,
                owed=summary.settlement,
                net_position=net_pos,
                recorded_settlements=records,
                remaining_balance=remaining,
                upload_statuses=upload_statuses,
                persons=ctx.persons,
                is_finalized=is_finalized,
                finalized_at=finalized_at,
                transaction_count=summary.transaction_count,
                latest_transaction_month=await get_latest_transaction_month(uow),
                finalization_warnings=warnings,
                payer_splits=audit.payer_splits,
                payer_group_splits=audit.payer_group_splits,
            )
