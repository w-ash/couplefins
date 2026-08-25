import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel

from src.application.use_cases._shared.settlement_math import LedgerSettlementRecord
from src.application.use_cases._shared.settlement_records import SettlementRecord
from src.application.use_cases.get_settle_up_data import GetSettleUpDataResult
from src.domain.entities.settlement import Settlement
from src.domain.entities.transaction import Transaction
from src.domain.reconciliation import (
    PayerGroupSummary,
    PayerSplitSummary,
)
from src.domain.settlement_matching import SettlementCandidate
from src.interface.api.schemas.dashboard import DashboardPersonResponse
from src.interface.api.schemas.ledger import (
    LedgerMonthResponse,
    LedgerYearResponse,
)
from src.interface.api.schemas.reconciliation import (
    MonthReference,
    UploadStatusResponse,
)
from src.interface.api.schemas.types import MoneyField


class RecordSettlementRequest(BaseModel):
    amount: MoneyField
    from_person_id: UUID
    to_person_id: UUID
    method: str
    notes: str = ""
    settled_at: datetime.datetime | None = None
    # Transfer legs (the Venmo rows themselves) — excluded from math.
    linked_transaction_ids: list[UUID] = []
    # The months this payment covers; empty means the settled_at month.
    # Per-month portions are allocated at record time and stored.
    # Bounds live on MonthReference's fields (→ 422).
    covered_months: list[MonthReference] = []


class RecordWaivedSettlementRequest(BaseModel):
    from_person_id: UUID
    to_person_id: UUID
    # Calendar year whose balance is waived; omit to waive every open month.
    waive_year: int | None = None
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
    def from_domain(cls, settlement: Settlement) -> Self:
        return cls.from_record(
            SettlementRecord(settlement=settlement, linked_transaction_ids=[])
        )

    @classmethod
    def from_record(cls, record: SettlementRecord) -> Self:
        s = record.settlement
        return cls(
            id=s.id,
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


class SettlementPortionResponse(BaseModel):
    """One month's slice of a settlement payment."""

    year: int
    month: int
    amount: MoneyField


class LedgerSettlementResponse(SettlementResponse):
    """History entry enriched with its per-month portions."""

    portions: list[SettlementPortionResponse] = []

    @classmethod
    def from_ledger_record(
        cls, entry: LedgerSettlementRecord
    ) -> LedgerSettlementResponse:
        response = cls.from_record(entry.record)
        response.portions = [
            SettlementPortionResponse(year=p.year, month=p.month, amount=p.amount)
            for p in entry.application.portions
        ]
        return response


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
    """Everything Settle Up renders, precomputed and direction-resolved.

    The client scopes ``years``/``months``/``settlements`` to its selected
    year by field equality — it never does arithmetic.
    """

    year: int
    month: int
    years: list[LedgerYearResponse]
    months: list[LedgerMonthResponse]
    settlements: list[LedgerSettlementResponse]
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
            years=[LedgerYearResponse.from_domain(row) for row in result.years],
            months=[LedgerMonthResponse.from_domain(m) for m in result.months],
            settlements=[
                LedgerSettlementResponse.from_ledger_record(entry)
                for entry in result.settlements
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
