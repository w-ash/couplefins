from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from src.application.use_cases._shared.command_validators import Scope
from src.application.use_cases.get_dashboard import GetDashboardResult
from src.domain.budget import HealthStatus
from src.interface.api.schemas.reconciliation import (
    OwedAmountResponse,
    PersonSummaryResponse,
    UploadStatusResponse,
)


def _opt_float(v: Decimal | None) -> float | None:
    return float(v) if v is not None else None


class MonthHistoryEntryResponse(BaseModel):
    year: int
    month: int
    total_household_spending: float
    settlement_amount: float
    settlement_from_person_id: UUID | None
    settlement_to_person_id: UUID | None
    is_finalized: bool
    is_settled: bool
    settled_at: datetime | None
    total_all_spending: float | None = None


class PersonalMonthHistoryEntryResponse(BaseModel):
    year: int
    month: int
    total_spending: float
    household_portion: float
    own_spending: float


class BudgetAlertResponse(BaseModel):
    group_id: UUID
    group_name: str
    monthly_budget: float
    monthly_spent: float
    health: HealthStatus


class DashboardPersonResponse(BaseModel):
    id: UUID
    name: str


class DashboardResponse(BaseModel):
    scope: Scope
    current_person_id: UUID | None
    current_month_year: int
    current_month_month: int
    current_month_total_household_spending: float
    current_month_net_household_spending: float
    current_month_transaction_count: int
    current_month_person_summaries: list[PersonSummaryResponse]
    current_month_settlement: OwedAmountResponse | None
    current_month_net_settlement: OwedAmountResponse | None
    upload_statuses: list[UploadStatusResponse]
    household_spending_month: float
    household_spending_ytd: float
    ytd_settlement: OwedAmountResponse | None
    ytd_net_settlement: OwedAmountResponse | None
    ytd_total_settled: float
    month_history: list[MonthHistoryEntryResponse]
    persons: list[DashboardPersonResponse]
    unmapped_categories: list[str]
    is_finalized: bool
    finalized_at: datetime | None
    # Personal scope
    my_spending_month: float | None = None
    my_household_share_month: float | None = None
    my_personal_spending_month: float | None = None
    my_spending_ytd: float | None = None
    personal_month_history: list[PersonalMonthHistoryEntryResponse] | None = None
    budget_alerts: list[BudgetAlertResponse] | None = None
    # All scope
    total_all_spending_month: float | None = None
    total_all_spending_ytd: float | None = None

    @classmethod
    def from_result(cls, result: GetDashboardResult) -> DashboardResponse:
        cm = result.current_month
        return cls(
            scope=result.scope,
            current_person_id=result.current_person_id,
            current_month_year=cm.start_date.year,
            current_month_month=cm.start_date.month,
            current_month_total_household_spending=float(cm.total_household_spending),
            current_month_net_household_spending=float(cm.net_household_spending),
            current_month_transaction_count=cm.transaction_count,
            current_month_person_summaries=[
                PersonSummaryResponse.from_domain(ps) for ps in cm.person_summaries
            ],
            current_month_settlement=(
                OwedAmountResponse.from_domain(cm.settlement) if cm.settlement else None
            ),
            current_month_net_settlement=(
                OwedAmountResponse.from_domain(result.current_month_net_settlement)
                if result.current_month_net_settlement
                else None
            ),
            upload_statuses=[
                UploadStatusResponse.from_domain(us) for us in result.upload_statuses
            ],
            household_spending_month=float(result.household_spending_month),
            household_spending_ytd=float(result.household_spending_ytd),
            ytd_settlement=(
                OwedAmountResponse.from_domain(result.ytd_settlement)
                if result.ytd_settlement
                else None
            ),
            ytd_net_settlement=(
                OwedAmountResponse.from_domain(result.ytd_net_settlement)
                if result.ytd_net_settlement
                else None
            ),
            ytd_total_settled=float(result.ytd_total_settled),
            month_history=[
                MonthHistoryEntryResponse(
                    year=mh.year,
                    month=mh.month,
                    total_household_spending=float(mh.total_household_spending),
                    settlement_amount=float(mh.settlement_amount),
                    settlement_from_person_id=mh.settlement_from_person_id,
                    settlement_to_person_id=mh.settlement_to_person_id,
                    is_finalized=mh.is_finalized,
                    is_settled=mh.is_settled,
                    settled_at=mh.settled_at,
                    total_all_spending=_opt_float(mh.total_all_spending),
                )
                for mh in result.month_history
            ],
            persons=[
                DashboardPersonResponse(id=p.id, name=p.name) for p in result.persons
            ],
            unmapped_categories=result.unmapped_categories,
            is_finalized=result.is_finalized,
            finalized_at=result.finalized_at,
            my_spending_month=_opt_float(result.my_spending_month),
            my_household_share_month=_opt_float(result.my_household_share_month),
            my_personal_spending_month=_opt_float(result.my_personal_spending_month),
            my_spending_ytd=_opt_float(result.my_spending_ytd),
            personal_month_history=(
                [
                    PersonalMonthHistoryEntryResponse(
                        year=pmh.year,
                        month=pmh.month,
                        total_spending=float(pmh.total_spending),
                        household_portion=float(pmh.household_portion),
                        own_spending=float(pmh.own_spending),
                    )
                    for pmh in result.personal_month_history
                ]
                if result.personal_month_history is not None
                else None
            ),
            budget_alerts=(
                [
                    BudgetAlertResponse(
                        group_id=ba.group_id,
                        group_name=ba.group_name,
                        monthly_budget=float(ba.monthly_budget),
                        monthly_spent=float(ba.monthly_spent),
                        health=ba.health,
                    )
                    for ba in result.budget_alerts
                ]
                if result.budget_alerts is not None
                else None
            ),
            total_all_spending_month=_opt_float(result.total_all_spending_month),
            total_all_spending_ytd=_opt_float(result.total_all_spending_ytd),
        )
