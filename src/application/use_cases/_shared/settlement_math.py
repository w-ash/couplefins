from decimal import Decimal

from attrs import define

from src.application.use_cases._shared.date_math import month_bounds
from src.application.use_cases._shared.reconciliation_context import (
    ReconciliationContext,
)
from src.application.use_cases._shared.settlement_records import (
    SettlementRecord,
    enrich_with_links,
)
from src.application.use_cases._shared.upload_status import (
    UploadStatus,
    build_upload_statuses,
)
from src.domain.entities.transaction import Transaction
from src.domain.reconciliation import (
    ReconciliationSummary,
    SettlementResult,
    compute_net_position,
    reconcile,
)
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class MonthSettlementSnapshot:
    transactions: list[Transaction]
    summary: ReconciliationSummary
    records: list[SettlementRecord]
    net_position: SettlementResult | None
    upload_statuses: list[UploadStatus]

    @property
    def remaining(self) -> Decimal:
        return self.net_position.amount if self.net_position else Decimal(0)


async def load_month_settlement_snapshot(
    uow: UnitOfWorkProtocol,
    year: int,
    month: int,
    ctx: ReconciliationContext,
) -> MonthSettlementSnapshot:
    start, end = month_bounds(year, month)
    # Settlement relevance is payer_percentage < 100, independent of the
    # household flag — spotted and personal-split rows enter the math.
    transactions = await uow.transactions.get_settlement_relevant_by_date_range(
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

    records = await enrich_with_links(
        await uow.settlements.get_by_period(year, month), uow
    )

    net_position = compute_net_position(
        summary.settlement,
        [r.settlement for r in records],
    )

    upload_statuses = build_upload_statuses(
        ctx.persons,
        await uow.uploads.get_by_person_ids_with_transactions_in_date_range(
            ctx.person_ids, start, end
        ),
    )

    return MonthSettlementSnapshot(
        transactions=transactions,
        summary=summary,
        records=records,
        net_position=net_position,
        upload_statuses=upload_statuses,
    )
