import datetime
from uuid import UUID

from pydantic import BaseModel

from src.application.use_cases._shared.settlement_math import LedgerSettlementRecord
from src.application.use_cases._shared.settlement_records import SettlementRecord
from src.application.use_cases.get_settle_up_data import GetSettleUpDataResult
from src.domain.entities.settlement import Settlement
from src.domain.entities.transaction import Transaction
from src.domain.ledger import LedgerMonth
from src.domain.reconciliation import PayerGroupSummary, PayerSplitSummary
from src.domain.settlement_matching import SettlementCandidate
from src.interface.api.schemas.dashboard import DashboardPersonResponse
from src.interface.api.schemas.reconciliation import (
    MonthReference,
    MonthSpanResponse,
    OwedAmountResponse,
    UploadStatusResponse,
)
from src.interface.api.schemas.types import MoneyField


class RecordSettlementRequest(BaseModel):
    # Optional "recorded against" annotation — display only, never math.
    year: int | None = None
    month: int | None = None
    amount: MoneyField
    from_person_id: UUID
    to_person_id: UUID
    method: str
    notes: str = ""
    settled_at: datetime.datetime | None = None
    linked_transaction_ids: list[UUID] = []


class RecordWaivedSettlementRequest(BaseModel):
    # Optional "recorded against" annotation — display only, never math.
    year: int | None = None
    month: int | None = None
    from_person_id: UUID
    to_person_id: UUID
    notes: str = ""


class MarkTransactionRequest(BaseModel):
    transaction_id: UUID
    settlement_id: UUID | None = None
    is_settlement: bool = True


class LinkedTransactionResponse(BaseModel):
    id: UUID
    date: datetime.date
    merchant: str
    amount: MoneyField
    payer_person_id: UUID

    @classmethod
    def from_domain(cls, tx: Transaction) -> LinkedTransactionResponse:
        return cls(
            id=tx.id,
            date=tx.date,
            merchant=tx.merchant,
            amount=tx.amount,
            payer_person_id=tx.payer_person_id,
        )


class SettlementResponse(BaseModel):
    id: UUID
    # Optional "recorded against" annotation — display metadata, never math.
    year: int | None
    month: int | None
    amount: MoneyField
    from_person_id: UUID
    to_person_id: UUID
    method: str | None
    is_waived: bool
    notes: str
    settled_at: datetime.datetime
    created_at: datetime.datetime
    linked_transaction_ids: list[UUID]
    linked_transactions: list[LinkedTransactionResponse] = []

    @classmethod
    def from_domain(
        cls, settlement: Settlement, linked_tx_ids: list[UUID] | None = None
    ) -> SettlementResponse:
        return cls(
            id=settlement.id,
            year=settlement.year,
            month=settlement.month,
            amount=settlement.amount,
            from_person_id=settlement.from_person_id,
            to_person_id=settlement.to_person_id,
            method=settlement.method,
            is_waived=settlement.is_waived,
            notes=settlement.notes,
            settled_at=settlement.settled_at,
            created_at=settlement.created_at,
            linked_transaction_ids=linked_tx_ids or [],
        )

    @classmethod
    def from_record(cls, record: SettlementRecord) -> SettlementResponse:
        s = record.settlement
        return cls(
            id=s.id,
            year=s.year,
            month=s.month,
            amount=s.amount,
            from_person_id=s.from_person_id,
            to_person_id=s.to_person_id,
            method=s.method,
            is_waived=s.is_waived,
            notes=s.notes,
            settled_at=s.settled_at,
            created_at=s.created_at,
            linked_transaction_ids=record.linked_transaction_ids,
            linked_transactions=[
                LinkedTransactionResponse.from_domain(tx)
                for tx in record.linked_transactions
            ],
        )


class CoveredMonthResponse(BaseModel):
    """One (month, amount) slice a payment covered, per FIFO."""

    year: int
    month: int
    amount: MoneyField


class LedgerSettlementResponse(SettlementResponse):
    """Payment history entry enriched with its FIFO coverage."""

    covered: list[CoveredMonthResponse]
    unapplied: MoneyField

    @classmethod
    def from_ledger_record(
        cls, entry: LedgerSettlementRecord
    ) -> LedgerSettlementResponse:
        base = SettlementResponse.from_record(entry.record)
        return cls.model_validate({
            **base.model_dump(),
            "covered": [
                {"year": year, "month": month, "amount": amount}
                for year, month, amount in entry.coverage.covered
            ],
            "unapplied": entry.coverage.unapplied,
        })


class LedgerMonthResponse(BaseModel):
    """One month's ledger row: gross position, applied payments, status."""

    year: int
    month: int
    gross: OwedAmountResponse | None
    applied: MoneyField
    remaining: MoneyField
    status: str  # settled | partially_settled | carried_forward
    covering_settlement_ids: list[UUID]
    is_offset: bool

    @classmethod
    def from_domain(cls, month: LedgerMonth) -> LedgerMonthResponse:
        return cls(
            year=month.year,
            month=month.month,
            # A zero-amount gross carries an arbitrary direction — omit it.
            gross=(
                OwedAmountResponse.from_domain(month.gross)
                if month.gross and month.gross.amount > 0
                else None
            ),
            applied=month.applied,
            remaining=month.remaining,
            status=month.status,
            covering_settlement_ids=list(month.covering_settlement_ids),
            is_offset=month.is_offset,
        )


class SettlementCandidateResponse(BaseModel):
    id: UUID
    date: datetime.date
    merchant: str
    amount: MoneyField
    payer_person_id: UUID
    category: str
    score: int
    match_reasons: list[str]

    @classmethod
    def from_domain(cls, candidate: SettlementCandidate) -> SettlementCandidateResponse:
        tx = candidate.transaction
        return cls(
            id=tx.id,
            date=tx.date,
            merchant=tx.merchant,
            amount=tx.amount,
            payer_person_id=tx.payer_person_id,
            category=tx.category,
            score=candidate.score,
            match_reasons=list(candidate.match_reasons),
        )


class PayerSplitSummaryResponse(BaseModel):
    """Per-payer aggregate over split transactions for the audit table."""

    payer_person_id: UUID
    fronted: MoneyField
    their_share: MoneyField
    partner_share: MoneyField
    transaction_count: int

    @classmethod
    def from_domain(cls, ps: PayerSplitSummary) -> PayerSplitSummaryResponse:
        return cls(
            payer_person_id=ps.payer_person_id,
            fronted=ps.total_paid,
            their_share=ps.total_share,
            partner_share=ps.total_paid - ps.total_share,
            transaction_count=ps.transaction_count,
        )


class PayerGroupSplitSummaryResponse(BaseModel):
    """Per-(payer x category-group) aggregate for the audit table."""

    payer_person_id: UUID
    group_id: UUID | None
    group_name: str
    fronted: MoneyField
    their_share: MoneyField
    partner_share: MoneyField
    transaction_count: int
    categories: list[str]

    @classmethod
    def from_domain(cls, ps: PayerGroupSummary) -> PayerGroupSplitSummaryResponse:
        return cls(
            payer_person_id=ps.payer_person_id,
            group_id=ps.group_id,
            group_name=ps.group_name,
            fronted=ps.total_paid,
            their_share=ps.total_share,
            partner_share=ps.total_paid - ps.total_share,
            transaction_count=ps.transaction_count,
            categories=ps.categories,
        )


class SettleUpDataResponse(BaseModel):
    year: int
    month: int
    owed: OwedAmountResponse | None
    net_position: OwedAmountResponse | None
    recorded_settlements: list[SettlementResponse]
    remaining_balance: MoneyField
    outstanding: OwedAmountResponse | None
    outstanding_span: MonthSpanResponse | None
    ledger_months: list[LedgerMonthResponse]
    all_settlements: list[LedgerSettlementResponse]
    upload_statuses: list[UploadStatusResponse]
    persons: list[DashboardPersonResponse]
    is_finalized: bool
    finalized_at: datetime.datetime | None
    transaction_count: int
    latest_transaction_month: MonthReference | None
    finalization_warnings: list[str]
    payer_splits: list[PayerSplitSummaryResponse]
    payer_group_splits: list[PayerGroupSplitSummaryResponse]

    @classmethod
    def from_result(cls, result: GetSettleUpDataResult) -> SettleUpDataResponse:
        return cls(
            year=result.year,
            month=result.month,
            owed=OwedAmountResponse.from_domain(result.owed) if result.owed else None,
            net_position=OwedAmountResponse.from_domain(result.net_position)
            if result.net_position
            else None,
            recorded_settlements=[
                SettlementResponse.from_record(r) for r in result.recorded_settlements
            ],
            remaining_balance=result.remaining_balance,
            outstanding=(
                OwedAmountResponse.from_domain(result.outstanding)
                if result.outstanding
                else None
            ),
            outstanding_span=MonthSpanResponse.from_optional_span(
                result.outstanding_span
            ),
            ledger_months=[
                LedgerMonthResponse.from_domain(m) for m in result.ledger_months
            ],
            all_settlements=[
                LedgerSettlementResponse.from_ledger_record(entry)
                for entry in result.all_settlements
            ],
            upload_statuses=[
                UploadStatusResponse.from_domain(us) for us in result.upload_statuses
            ],
            persons=[
                DashboardPersonResponse(id=p.id, name=p.name) for p in result.persons
            ],
            is_finalized=result.is_finalized,
            finalized_at=result.finalized_at,
            transaction_count=result.transaction_count,
            latest_transaction_month=MonthReference.from_optional_tuple(
                result.latest_transaction_month
            ),
            finalization_warnings=result.finalization_warnings,
            payer_splits=[
                PayerSplitSummaryResponse.from_domain(ps) for ps in result.payer_splits
            ],
            payer_group_splits=[
                PayerGroupSplitSummaryResponse.from_domain(ps)
                for ps in result.payer_group_splits
            ],
        )


class RecordSettlementResponse(BaseModel):
    settlement: SettlementResponse
    warnings: list[str]


class DeleteSettlementResponse(BaseModel):
    deleted: bool


class MarkTransactionResponse(BaseModel):
    transaction_id: UUID
    is_settlement: bool
