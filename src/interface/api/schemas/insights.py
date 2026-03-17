from uuid import UUID

from pydantic import BaseModel

from src.application.use_cases.get_spending_trends import GetSpendingTrendsResult


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


class SpendingTrendsResponse(BaseModel):
    year: int
    monthly_group_spending: list[MonthlyGroupSpendingItem]
    monthly_totals: list[MonthlyTotalItem]
    group_summaries: list[GroupSummaryItem]

    @classmethod
    def from_result(cls, result: GetSpendingTrendsResult) -> SpendingTrendsResponse:
        return cls(
            year=result.year,
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
        )
