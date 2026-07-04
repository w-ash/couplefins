from uuid import UUID

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
from src.domain.entities.settlement import Settlement
from src.domain.entities.transaction import Transaction
from src.domain.ledger import (
    PaymentCoverage,
    SettlementLedger,
    compute_ledger,
    empty_payment_coverage,
)
from src.domain.reconciliation import ReconciliationSummary, reconcile
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class LedgerSettlementRecord:
    """One payment enriched with its links and FIFO coverage."""

    record: SettlementRecord
    coverage: PaymentCoverage


@define(frozen=True, slots=True)
class LedgerBundle:
    """The all-time settlement ledger plus its enriched payment history.

    ``records`` is chronological by ``(settled_at, created_at, id)``,
    matching the order of ``ledger.payments``.
    """

    ledger: SettlementLedger
    settlements: list[Settlement]
    records: list[LedgerSettlementRecord]


async def load_settlement_ledger(
    uow: UnitOfWorkProtocol,
    ctx: ReconciliationContext,
) -> LedgerBundle:
    """Compute the running settlement ledger over all-time data."""
    transactions = await uow.transactions.get_all_settlement_relevant()
    settlements = await uow.settlements.get_all()
    ledger = compute_ledger(transactions, settlements, ctx.person_ids)

    ordered = sorted(settlements, key=lambda s: (s.settled_at, s.created_at, s.id))
    coverage_by_id: dict[UUID, PaymentCoverage] = {
        c.settlement_id: c for c in ledger.payments
    }
    records = [
        LedgerSettlementRecord(
            record=record,
            # compute_ledger yields no coverages before couple setup is
            # complete (person count != 2) — degrade to empty coverage.
            coverage=coverage_by_id.get(
                record.settlement.id, empty_payment_coverage(record.settlement.id)
            ),
        )
        for record in await enrich_with_links(ordered, uow)
    ]
    return LedgerBundle(ledger=ledger, settlements=settlements, records=records)


@define(frozen=True, slots=True)
class MonthAuditSnapshot:
    """Month-scoped audit data for the Settle Up drill-down.

    Balances live on the ledger (see ``load_settlement_ledger``); this
    snapshot carries the month's reconcile() summary (audit splits), its
    month-annotated payment records, and upload statuses.
    """

    transactions: list[Transaction]
    summary: ReconciliationSummary
    records: list[SettlementRecord]
    upload_statuses: list[UploadStatus]


async def load_month_audit_snapshot(
    uow: UnitOfWorkProtocol,
    year: int,
    month: int,
    ctx: ReconciliationContext,
) -> MonthAuditSnapshot:
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

    upload_statuses = build_upload_statuses(
        ctx.persons,
        await uow.uploads.get_by_person_ids_with_transactions_in_date_range(
            ctx.person_ids, start, end
        ),
    )

    return MonthAuditSnapshot(
        transactions=transactions,
        summary=summary,
        records=records,
        upload_statuses=upload_statuses,
    )
