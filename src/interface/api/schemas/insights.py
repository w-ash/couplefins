from uuid import UUID

from pydantic import BaseModel

from src.application.use_cases.get_spending_trends import GetSpendingTrendsResult
from src.interface.api.schemas.persons import PersonResponse


class MonthlyGroupSpendingItem(BaseModel):
    year: int
    month: int
    group_id: UUID | None
    group_name: str
    amount: float


class MonthlyTotalItem(BaseModel):
    year: int
    month: int
    total_amount: float


class GroupSummaryItem(BaseModel):
    group_id: UUID | None
    group_name: str
    ytd_total: float
    transaction_count: int


class GroupComparisonItem(BaseModel):
    group_id: UUID | None
    group_name: str
    current_month_amount: float
    trailing_average: float
    delta_amount: float
    delta_percentage: float


class BudgetLineItem(BaseModel):
    group_id: UUID
    monthly_budget: float


class MonthlySettlementItem(BaseModel):
    year: int
    month: int
    amount: float
    from_person_id: UUID
    to_person_id: UUID
    is_settled: bool


class SpendingTrendsResponse(BaseModel):
    year: int
    month: int
    monthly_group_spending: list[MonthlyGroupSpendingItem]
    monthly_totals: list[MonthlyTotalItem]
    group_summaries: list[GroupSummaryItem]
    comparison_cards: list[GroupComparisonItem]
    budget_lines: list[BudgetLineItem]
    settlement_trend: list[MonthlySettlementItem]
    persons: list[PersonResponse]

    @classmethod
    def from_result(cls, result: GetSpendingTrendsResult) -> SpendingTrendsResponse:
        return cls(
            year=result.year,
            month=result.month,
            monthly_group_spending=[
                MonthlyGroupSpendingItem(
                    year=mgs.year,
                    month=mgs.month,
                    group_id=mgs.group_id,
                    group_name=mgs.group_name,
                    amount=float(mgs.amount),
                )
                for mgs in result.trends.monthly_group_spending
            ],
            monthly_totals=[
                MonthlyTotalItem(
                    year=mt.year,
                    month=mt.month,
                    total_amount=float(mt.total_amount),
                )
                for mt in result.trends.monthly_totals
            ],
            group_summaries=[
                GroupSummaryItem(
                    group_id=gs.group_id,
                    group_name=gs.group_name,
                    ytd_total=float(gs.ytd_total),
                    transaction_count=gs.transaction_count,
                )
                for gs in result.trends.group_summaries
            ],
            comparison_cards=[
                GroupComparisonItem(
                    group_id=cc.group_id,
                    group_name=cc.group_name,
                    current_month_amount=float(cc.current_month_amount),
                    trailing_average=float(cc.trailing_average),
                    delta_amount=float(cc.delta_amount),
                    delta_percentage=float(cc.delta_percentage),
                )
                for cc in result.comparison_cards
            ],
            budget_lines=[
                BudgetLineItem(
                    group_id=gid,
                    monthly_budget=float(amount),
                )
                for gid, amount in result.budget_lines.items()
            ],
            settlement_trend=[
                MonthlySettlementItem(
                    year=ms.year,
                    month=ms.month,
                    amount=float(ms.amount),
                    from_person_id=ms.from_person_id,
                    to_person_id=ms.to_person_id,
                    is_settled=ms.is_settled,
                )
                for ms in result.settlement_trend
            ],
            persons=[
                PersonResponse(
                    id=p.id,
                    name=p.name,
                    adjustment_account=p.adjustment_account,
                )
                for p in result.persons
            ],
        )
