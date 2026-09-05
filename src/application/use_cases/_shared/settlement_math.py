from attrs import define

from src.application.use_cases._shared.date_math import month_bounds
from src.application.use_cases._shared.reconciliation_context import (
    ReconciliationContext,
)
from src.application.use_cases._shared.settlement_records import (
    SettlementRecord,
    enrich_with_links,
)
from src.application.use_cases._shared.transaction_reads import (
    fetch_all_settlement_rows,
)
from src.application.use_cases._shared.upload_status import (
    UploadStatus,
    build_upload_statuses,
)
from src.domain.entities.settlement import Settlement
from src.domain.entities.transaction import Transaction
from src.domain.ledger import (
    LedgerSettlement,
    SettlementLedger,
    compute_ledger,
)
from src.domain.reconciliation import ReconciliationSummary, reconcile
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class LedgerSettlementRecord:
    """One settlement enriched with its links and resolved portions."""

    record: SettlementRecord  # settlement + its transfer legs
    application: LedgerSettlement  # resolved per-month portions


@define(frozen=True, slots=True)
class LedgerBundle:
    """The settlement ledger plus its enriched settlement history.

    ``records`` is chronological by ``(settled_at, created_at, id)``,
    matching the order of ``ledger.settlements``.
    """

    ledger: SettlementLedger
    records: list[LedgerSettlementRecord]
    # All-time settlement-relevant transactions the ledger was computed
    # from — reusable for month-scoped views without another query.
    transactions: list[Transaction]


@define(frozen=True, slots=True)
class LoadedLedger:
    """The settlement ledger plus the settlements it was computed from."""

    ledger: SettlementLedger
    settlements: list[Settlement]
    # All-time settlement-relevant transactions the ledger was computed from.
    transactions: list[Transaction]


async def load_ledger(
    uow: UnitOfWorkProtocol,
    ctx: ReconciliationContext,
) -> LoadedLedger:
    """Compute the settlement ledger without link enrichment.

    Callers that only read ``ledger`` (and the raw settlement list) should use
    this — it skips the enrichment queries ``load_settlement_ledger`` pays
    for its ``records``.
    """
    transactions = await fetch_all_settlement_rows(uow, ctx)
    settlements = await uow.settlements.get_all()
    portions = await uow.settlement_portions.get_all()
    return LoadedLedger(
        ledger=compute_ledger(transactions, settlements, portions, ctx.person_ids),
        settlements=settlements,
        transactions=transactions,
    )


async def load_settlement_ledger(
    uow: UnitOfWorkProtocol,
    ctx: ReconciliationContext,
) -> LedgerBundle:
    """Compute the settlement ledger plus its enriched settlement history.

    Only ``get_settle_up_data`` needs ``records``; ledger-only callers should
    use ``load_ledger`` to avoid the enrichment I/O.
    """
    loaded = await load_ledger(uow, ctx)
    ledger, settlements = loaded.ledger, loaded.settlements

    ordered = sorted(settlements, key=lambda s: (s.settled_at, s.created_at, s.id))
    application_by_id = {a.settlement_id: a for a in ledger.settlements}
    records = [
        LedgerSettlementRecord(
            record=record,
            # compute_ledger yields no applications before couple setup is
            # complete (person count != 2) — degrade to an empty one.
            application=application_by_id.get(
                record.settlement.id,
                LedgerSettlement(settlement_id=record.settlement.id, portions=()),
            ),
        )
        for record in await enrich_with_links(ordered, uow)
    ]
    return LedgerBundle(
        ledger=ledger, records=records, transactions=loaded.transactions
    )


@define(frozen=True, slots=True)
class MonthAuditSnapshot:
    """Month-scoped audit data for the Settle Up drill-down.

    Balances live on the ledger (see ``load_settlement_ledger``); this
    snapshot carries the month's reconcile() summary (audit splits) and
    upload statuses.
    """

    transactions: list[Transaction]
    summary: ReconciliationSummary
    upload_statuses: list[UploadStatus]


async def load_month_audit_snapshot(
    uow: UnitOfWorkProtocol,
    year: int,
    month: int,
    ctx: ReconciliationContext,
    all_transactions: list[Transaction],
) -> MonthAuditSnapshot:
    """``all_transactions`` is the all-time settlement-relevant list the
    ledger was computed from — scoped to the month here, no re-query."""
    start, end = month_bounds(year, month)
    transactions = [tx for tx in all_transactions if start <= tx.date <= end]

    summary = reconcile(
        transactions,
        ctx.persons,
        ctx.categories,
        ctx.category_groups,
        start_date=start,
        end_date=end,
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
        upload_statuses=upload_statuses,
    )
