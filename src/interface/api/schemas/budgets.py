from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator

from src.application.use_cases.get_budget_overview import GetBudgetOverviewResult
from src.domain.budget import HealthStatus
from src.domain.entities.category_group_budget import CategoryGroupBudget


def _validate_positive_amount(v: Decimal) -> Decimal:
    if v <= 0:
        raise ValueError("monthly_amount must be positive")
    return v


class SaveBudgetRequest(BaseModel):
    group_id: UUID
    monthly_amount: Decimal
    effective_from: date

    @field_validator("monthly_amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        return _validate_positive_amount(v)


class UpdateBudgetRequest(BaseModel):
    monthly_amount: Decimal

    @field_validator("monthly_amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        return _validate_positive_amount(v)


class BudgetResponse(BaseModel):
    id: UUID
    group_id: UUID
    monthly_amount: float
    effective_from: date

    @classmethod
    def from_domain(cls, budget: CategoryGroupBudget) -> BudgetResponse:
        return cls(
            id=budget.id,
            group_id=budget.group_id,
            monthly_amount=float(budget.monthly_amount),
            effective_from=budget.effective_from,
        )


class CategorySpendResponse(BaseModel):
    category: str
    total_amount: float
    transaction_count: int


class GroupBudgetStatusResponse(BaseModel):
    group_id: UUID
    group_name: str
    budget_id: UUID | None
    monthly_budget: float | None
    monthly_spent: float
    ytd_budget: float | None
    ytd_spent: float
    monthly_health: HealthStatus | None
    ytd_health: HealthStatus | None
    average_monthly_spending: float
    categories: list[CategorySpendResponse]


class BudgetOverviewResponse(BaseModel):
    year: int
    month: int
    group_statuses: list[GroupBudgetStatusResponse]
    total_monthly_budget: float
    total_monthly_spent: float
    total_ytd_budget: float
    total_ytd_spent: float
    budgets: list[BudgetResponse]

    @classmethod
    def from_result(cls, result: GetBudgetOverviewResult) -> BudgetOverviewResponse:
        overview = result.overview
        return cls(
            year=overview.year,
            month=overview.month,
            group_statuses=[
                GroupBudgetStatusResponse(
                    group_id=s.group_id,
                    group_name=s.group_name,
                    budget_id=s.budget_id,
                    monthly_budget=float(s.monthly_budget)
                    if s.monthly_budget is not None
                    else None,
                    monthly_spent=float(s.monthly_spent),
                    ytd_budget=float(s.ytd_budget)
                    if s.ytd_budget is not None
                    else None,
                    ytd_spent=float(s.ytd_spent),
                    monthly_health=s.monthly_health,
                    ytd_health=s.ytd_health,
                    average_monthly_spending=float(s.average_monthly_spending),
                    categories=[
                        CategorySpendResponse(
                            category=c.category,
                            total_amount=float(c.total_amount),
                            transaction_count=c.transaction_count,
                        )
                        for c in s.categories
                    ],
                )
                for s in overview.group_statuses
            ],
            total_monthly_budget=float(overview.total_monthly_budget),
            total_monthly_spent=float(overview.total_monthly_spent),
            total_ytd_budget=float(overview.total_ytd_budget),
            total_ytd_spent=float(overview.total_ytd_spent),
            budgets=[BudgetResponse.from_domain(b) for b in result.budgets],
        )
