from uuid import UUID

from pydantic import BaseModel

from src.application.use_cases.get_spending_trends import GetSpendingTrendsResult
from src.domain.insights import MonthlyGroupSpending, SpendingFlow
from src.domain.spending_lens import FlowSourceKind
from src.interface.api.schemas.persons import PersonResponse
from src.interface.api.schemas.types import MoneyField


class MonthlyGroupSpendingItem(BaseModel):
    year: int
    month: int
    group_id: UUID | None
    group_name: str
    amount: MoneyField


class MonthlyTotalItem(BaseModel):
    year: int
    month: int
    total_amount: MoneyField


class GroupSummaryItem(BaseModel):
    group_id: UUID | None
    group_name: str
    ytd_total: MoneyField
    transaction_count: int


class GroupComparisonItem(BaseModel):
    group_id: UUID | None
    group_name: str
    current_month_amount: MoneyField
    trailing_average: MoneyField
    delta_amount: MoneyField
    delta_percentage: MoneyField
    is_new: bool


class CategoryComparisonItem(BaseModel):
    category: str
    group_id: UUID | None
    group_name: str
    current_month_amount: MoneyField
    trailing_average: MoneyField
    delta_amount: MoneyField
    delta_percentage: MoneyField
    is_new: bool


class SpendingFlowCellItem(BaseModel):
    source_kind: FlowSourceKind
    source_person_id: UUID
    group_id: UUID | None
    group_name: str
    category: str
    amount: MoneyField
    transaction_count: int


class TopMerchantItem(BaseModel):
    merchant: str
    amount: MoneyField
    transaction_count: int
    category: str
    group_id: UUID | None


class SpendingFlowItem(BaseModel):
    cells: list[SpendingFlowCellItem]
    top_merchants: list[TopMerchantItem]

    @classmethod
    def from_domain(cls, flow: SpendingFlow) -> SpendingFlowItem:
        return cls(
            cells=[
                SpendingFlowCellItem(
                    source_kind=c.source_kind,
                    source_person_id=c.source_person_id,
                    group_id=c.group_id,
                    group_name=c.group_name,
                    category=c.category,
                    amount=c.amount,
                    transaction_count=c.transaction_count,
                )
                for c in flow.cells
            ],
            top_merchants=[
                TopMerchantItem(
                    merchant=m.merchant,
                    amount=m.amount,
                    transaction_count=m.transaction_count,
                    category=m.category,
                    group_id=m.group_id,
                )
                for m in flow.top_merchants
            ],
        )


class SpendingTrendsResponse(BaseModel):
    year: int
    month: int
    monthly_group_spending: list[MonthlyGroupSpendingItem]
    monthly_totals: list[MonthlyTotalItem]
    group_summaries: list[GroupSummaryItem]
    comparison_cards: list[GroupComparisonItem]
    category_comparisons: list[CategoryComparisonItem]
    month_flow: SpendingFlowItem
    ytd_flow: SpendingFlowItem
    persons: list[PersonResponse]
    comparison_monthly_group_spending: list[MonthlyGroupSpendingItem]

    @classmethod
    def from_result(cls, result: GetSpendingTrendsResult) -> SpendingTrendsResponse:
        def _map_spending(
            mgs_list: list[MonthlyGroupSpending],
        ) -> list[MonthlyGroupSpendingItem]:
            return [
                MonthlyGroupSpendingItem(
                    year=mgs.year,
                    month=mgs.month,
                    group_id=mgs.group_id,
                    group_name=mgs.group_name,
                    amount=mgs.amount,
                )
                for mgs in mgs_list
            ]

        return cls(
            year=result.year,
            month=result.month,
            monthly_group_spending=_map_spending(result.trends.monthly_group_spending),
            monthly_totals=[
                MonthlyTotalItem(
                    year=mt.year,
                    month=mt.month,
                    total_amount=mt.total_amount,
                )
                for mt in result.trends.monthly_totals
            ],
            group_summaries=[
                GroupSummaryItem(
                    group_id=gs.group_id,
                    group_name=gs.group_name,
                    ytd_total=gs.ytd_total,
                    transaction_count=gs.transaction_count,
                )
                for gs in result.trends.group_summaries
            ],
            comparison_cards=[
                GroupComparisonItem(
                    group_id=cc.group_id,
                    group_name=cc.group_name,
                    current_month_amount=cc.current_month_amount,
                    trailing_average=cc.trailing_average,
                    delta_amount=cc.delta_amount,
                    delta_percentage=cc.delta_percentage,
                    is_new=cc.is_new,
                )
                for cc in result.comparison_cards
            ],
            category_comparisons=[
                CategoryComparisonItem(
                    category=cc.category,
                    group_id=cc.group_id,
                    group_name=cc.group_name,
                    current_month_amount=cc.current_month_amount,
                    trailing_average=cc.trailing_average,
                    delta_amount=cc.delta_amount,
                    delta_percentage=cc.delta_percentage,
                    is_new=cc.is_new,
                )
                for cc in result.category_comparisons
            ],
            month_flow=SpendingFlowItem.from_domain(result.month_flow),
            ytd_flow=SpendingFlowItem.from_domain(result.ytd_flow),
            persons=[PersonResponse.from_domain(p) for p in result.persons],
            comparison_monthly_group_spending=_map_spending(
                result.comparison_monthly_group_spending
            ),
        )
