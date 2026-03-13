import datetime
from uuid import UUID

from pydantic import BaseModel

from src.application.use_cases._shared.upload_status import UploadStatus
from src.application.use_cases.get_reconciliation import GetReconciliationResult
from src.domain.entities.reconciliation_period import ReconciliationPeriod
from src.domain.reconciliation import PersonSummary, SettlementResult


class UploadStatusResponse(BaseModel):
    person_id: UUID
    person_name: str
    has_uploaded: bool
    upload_count: int

    @classmethod
    def from_domain(cls, us: UploadStatus) -> UploadStatusResponse:
        return cls(
            person_id=us.person_id,
            person_name=us.person_name,
            has_uploaded=us.has_uploaded,
            upload_count=us.upload_count,
        )


class SettlementResponse(BaseModel):
    amount: float
    from_person_id: UUID
    to_person_id: UUID

    @classmethod
    def from_domain(cls, sr: SettlementResult) -> SettlementResponse:
        return cls(
            amount=float(sr.amount),
            from_person_id=sr.from_person_id,
            to_person_id=sr.to_person_id,
        )


class PersonSummaryResponse(BaseModel):
    person_id: UUID
    total_paid: float
    total_share: float

    @classmethod
    def from_domain(cls, ps: PersonSummary) -> PersonSummaryResponse:
        return cls(
            person_id=ps.person_id,
            total_paid=float(ps.total_paid),
            total_share=float(ps.total_share),
        )


class CategoryBreakdownResponse(BaseModel):
    category: str
    group_id: UUID | None
    group_name: str
    total_amount: float
    transaction_count: int


class CategoryGroupBreakdownResponse(BaseModel):
    group_id: UUID | None
    group_name: str
    total_amount: float
    transaction_count: int
    categories: list[CategoryBreakdownResponse]


class TransactionResponse(BaseModel):
    id: UUID
    date: datetime.date
    merchant: str
    category: str
    account: str
    amount: float
    notes: str
    tags: list[str]
    payer_person_id: UUID
    payer_percentage: int | None
    original_date: datetime.date | None
    original_amount: float | None


class FinalizePeriodRequest(BaseModel):
    year: int
    month: int
    notes: str = ""


class UnfinalizePeriodRequest(BaseModel):
    year: int
    month: int


class PeriodStatusResponse(BaseModel):
    is_finalized: bool
    finalized_at: datetime.datetime | None
    notes: str

    @classmethod
    def from_domain(cls, period: ReconciliationPeriod | None) -> PeriodStatusResponse:
        if period is None:
            return cls(is_finalized=False, finalized_at=None, notes="")
        return cls(
            is_finalized=period.is_finalized,
            finalized_at=period.finalized_at,
            notes=period.notes,
        )


class ReconciliationResponse(BaseModel):
    start_date: datetime.date
    end_date: datetime.date
    year: int | None
    month: int | None
    total_shared_spending: float
    total_shared_refunds: float
    net_shared_spending: float
    person_summaries: list[PersonSummaryResponse]
    settlement: SettlementResponse | None
    category_group_breakdowns: list[CategoryGroupBreakdownResponse]
    transaction_count: int
    transactions: list[TransactionResponse]
    upload_statuses: list[UploadStatusResponse]
    unmapped_categories: list[str]
    is_finalized: bool | None
    finalized_at: datetime.datetime | None

    @classmethod
    def from_result(cls, result: GetReconciliationResult) -> ReconciliationResponse:
        summary = result.summary

        return cls(
            start_date=summary.start_date,
            end_date=summary.end_date,
            year=result.year,
            month=result.month,
            total_shared_spending=float(summary.total_shared_spending),
            total_shared_refunds=float(summary.total_shared_refunds),
            net_shared_spending=float(summary.net_shared_spending),
            person_summaries=[
                PersonSummaryResponse.from_domain(ps) for ps in summary.person_summaries
            ],
            settlement=(
                SettlementResponse.from_domain(summary.settlement)
                if summary.settlement
                else None
            ),
            category_group_breakdowns=[
                CategoryGroupBreakdownResponse(
                    group_id=gb.group_id,
                    group_name=gb.group_name,
                    total_amount=float(gb.total_amount),
                    transaction_count=gb.transaction_count,
                    categories=[
                        CategoryBreakdownResponse(
                            category=cb.category,
                            group_id=cb.group_id,
                            group_name=cb.group_name,
                            total_amount=float(cb.total_amount),
                            transaction_count=cb.transaction_count,
                        )
                        for cb in gb.categories
                    ],
                )
                for gb in summary.category_group_breakdowns
            ],
            transaction_count=summary.transaction_count,
            transactions=[
                TransactionResponse(
                    id=tx.id,
                    date=tx.date,
                    merchant=tx.merchant,
                    category=tx.category,
                    account=tx.account,
                    amount=float(tx.amount),
                    notes=tx.notes,
                    tags=list(tx.tags),
                    payer_person_id=tx.payer_person_id,
                    payer_percentage=tx.payer_percentage,
                    original_date=tx.original_date,
                    original_amount=(
                        float(tx.original_amount)
                        if tx.original_amount is not None
                        else None
                    ),
                )
                for tx in result.transactions
            ],
            upload_statuses=[
                UploadStatusResponse.from_domain(us) for us in result.upload_statuses
            ],
            unmapped_categories=result.unmapped_categories,
            is_finalized=result.is_finalized,
            finalized_at=result.finalized_at,
        )
