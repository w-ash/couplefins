from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.application.use_cases.get_dashboard import GetDashboardResult
from src.interface.api.schemas.reconciliation import (
    PersonSummaryResponse,
    SettlementResponse,
    UploadStatusResponse,
)


class MonthHistoryEntryResponse(BaseModel):
    year: int
    month: int
    total_shared_spending: float
    settlement_amount: float
    settlement_from_person_id: UUID | None
    settlement_to_person_id: UUID | None
    is_finalized: bool


class PersonResponse(BaseModel):
    id: UUID
    name: str


class DashboardResponse(BaseModel):
    current_month_year: int
    current_month_month: int
    current_month_total_shared_spending: float
    current_month_net_shared_spending: float
    current_month_transaction_count: int
    current_month_person_summaries: list[PersonSummaryResponse]
    current_month_settlement: SettlementResponse | None
    upload_statuses: list[UploadStatusResponse]
    ytd_total_shared_spending: float
    ytd_settlement: SettlementResponse | None
    month_history: list[MonthHistoryEntryResponse]
    persons: list[PersonResponse]
    unmapped_categories: list[str]
    is_finalized: bool
    finalized_at: datetime | None

    @classmethod
    def from_result(cls, result: GetDashboardResult) -> DashboardResponse:
        cm = result.current_month
        return cls(
            current_month_year=cm.year,
            current_month_month=cm.month,
            current_month_total_shared_spending=float(cm.total_shared_spending),
            current_month_net_shared_spending=float(cm.net_shared_spending),
            current_month_transaction_count=cm.transaction_count,
            current_month_person_summaries=[
                PersonSummaryResponse(
                    person_id=ps.person_id,
                    total_paid=float(ps.total_paid),
                    total_share=float(ps.total_share),
                )
                for ps in cm.person_summaries
            ],
            current_month_settlement=(
                SettlementResponse(
                    amount=float(cm.settlement.amount),
                    from_person_id=cm.settlement.from_person_id,
                    to_person_id=cm.settlement.to_person_id,
                )
                if cm.settlement
                else None
            ),
            upload_statuses=[
                UploadStatusResponse(
                    person_id=us.person_id,
                    person_name=us.person_name,
                    has_uploaded=us.has_uploaded,
                    upload_count=us.upload_count,
                )
                for us in result.upload_statuses
            ],
            ytd_total_shared_spending=float(result.ytd_total_shared_spending),
            ytd_settlement=(
                SettlementResponse(
                    amount=float(result.ytd_settlement.amount),
                    from_person_id=result.ytd_settlement.from_person_id,
                    to_person_id=result.ytd_settlement.to_person_id,
                )
                if result.ytd_settlement
                else None
            ),
            month_history=[
                MonthHistoryEntryResponse(
                    year=mh.year,
                    month=mh.month,
                    total_shared_spending=float(mh.total_shared_spending),
                    settlement_amount=float(mh.settlement_amount),
                    settlement_from_person_id=mh.settlement_from_person_id,
                    settlement_to_person_id=mh.settlement_to_person_id,
                    is_finalized=mh.is_finalized,
                )
                for mh in result.month_history
            ],
            persons=[PersonResponse(id=p.id, name=p.name) for p in result.persons],
            unmapped_categories=result.unmapped_categories,
            is_finalized=result.is_finalized,
            finalized_at=result.finalized_at,
        )
