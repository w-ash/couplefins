import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.application.use_cases._shared.upload_status import UploadStatus
from src.application.use_cases.get_reconciliation import GetReconciliationResult
from src.domain.entities.reconciliation_period import ReconciliationPeriod
from src.domain.reconciliation import PersonSummary, SettlementResult
from src.interface.api.schemas.types import MoneyField


class MonthReference(BaseModel):
    year: int = Field(ge=1)
    month: int = Field(ge=1, le=12)

    @classmethod
    def from_optional_tuple(cls, ym: tuple[int, int] | None) -> MonthReference | None:
        return cls(year=ym[0], month=ym[1]) if ym else None


class MonthSpanResponse(BaseModel):
    """Inclusive (start, end) month range, e.g. a ledger's outstanding span."""

    start: MonthReference
    end: MonthReference

    @classmethod
    def from_optional_span(
        cls, span: tuple[tuple[int, int], tuple[int, int]] | None
    ) -> MonthSpanResponse | None:
        if span is None:
            return None
        return cls(
            start=MonthReference(year=span[0][0], month=span[0][1]),
            end=MonthReference(year=span[1][0], month=span[1][1]),
        )


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


class OwedAmountResponse(BaseModel):
    amount: MoneyField
    from_person_id: UUID
    to_person_id: UUID

    @classmethod
    def from_domain(cls, sr: SettlementResult) -> OwedAmountResponse:
        return cls(
            amount=sr.amount,
            from_person_id=sr.from_person_id,
            to_person_id=sr.to_person_id,
        )


class PersonSummaryResponse(BaseModel):
    person_id: UUID
    total_paid: MoneyField
    total_share: MoneyField

    @classmethod
    def from_domain(cls, ps: PersonSummary) -> PersonSummaryResponse:
        return cls(
            person_id=ps.person_id,
            total_paid=ps.total_paid,
            total_share=ps.total_share,
        )


class CategoryBreakdownResponse(BaseModel):
    category: str
    group_id: UUID | None
    group_name: str
    total_amount: MoneyField
    transaction_count: int


class CategoryGroupBreakdownResponse(BaseModel):
    group_id: UUID | None
    group_name: str
    total_amount: MoneyField
    transaction_count: int
    categories: list[CategoryBreakdownResponse]


class TransactionResponse(BaseModel):
    id: UUID
    date: datetime.date
    merchant: str
    category: str
    account: str
    amount: MoneyField
    notes: str
    tags: list[str]
    payer_person_id: UUID
    payer_percentage: int
    household: bool
    is_excluded: bool
    is_settlement: bool
    # Row is money movement (transfer-kind category): listed, never counted.
    is_transfer: bool
    original_date: datetime.date | None
    original_amount: MoneyField | None


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
    total_household_spending: MoneyField
    total_household_refunds: MoneyField
    net_household_spending: MoneyField
    person_summaries: list[PersonSummaryResponse]
    settlement: OwedAmountResponse | None
    category_group_breakdowns: list[CategoryGroupBreakdownResponse]
    transaction_count: int
    transactions: list[TransactionResponse]
    upload_statuses: list[UploadStatusResponse]
    unmapped_categories: list[str]
    is_finalized: bool | None
    finalized_at: datetime.datetime | None
    latest_transaction_month: MonthReference | None

    @classmethod
    def from_result(cls, result: GetReconciliationResult) -> ReconciliationResponse:
        summary = result.summary

        return cls(
            start_date=summary.start_date,
            end_date=summary.end_date,
            year=result.year,
            month=result.month,
            total_household_spending=summary.total_household_spending,
            total_household_refunds=summary.total_household_refunds,
            net_household_spending=summary.net_household_spending,
            person_summaries=[
                PersonSummaryResponse.from_domain(ps) for ps in summary.person_summaries
            ],
            settlement=(
                OwedAmountResponse.from_domain(summary.settlement)
                if summary.settlement
                else None
            ),
            category_group_breakdowns=[
                CategoryGroupBreakdownResponse(
                    group_id=gb.group_id,
                    group_name=gb.group_name,
                    total_amount=gb.total_amount,
                    transaction_count=gb.transaction_count,
                    categories=[
                        CategoryBreakdownResponse(
                            category=cb.category,
                            group_id=cb.group_id,
                            group_name=cb.group_name,
                            total_amount=cb.total_amount,
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
                    amount=tx.amount,
                    notes=tx.notes,
                    tags=list(tx.tags),
                    payer_person_id=tx.payer_person_id,
                    payer_percentage=tx.payer_percentage,
                    household=tx.household,
                    is_excluded=tx.is_excluded,
                    is_settlement=tx.is_settlement,
                    is_transfer=tx.category in result.transfer_categories,
                    original_date=tx.original_date,
                    original_amount=tx.original_amount,
                )
                for tx in result.transactions
            ],
            upload_statuses=[
                UploadStatusResponse.from_domain(us) for us in result.upload_statuses
            ],
            unmapped_categories=result.unmapped_categories,
            is_finalized=result.is_finalized,
            finalized_at=result.finalized_at,
            latest_transaction_month=MonthReference.from_optional_tuple(
                result.latest_transaction_month
            ),
        )
