from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.application.use_cases._shared.command_validators import assert_positive_decimal
from src.application.use_cases.get_budget_overview import GetBudgetOverviewResult
from src.domain.budget import HealthStatus
from src.domain.entities.category_group_budget import CategoryGroupBudget


class SaveBudgetRequest(BaseModel):
    group_id: UUID
    monthly_amount: Decimal
    year: int = Field(ge=2020, le=2099)
    month: int = Field(ge=1, le=12)
    is_personal: bool = False

    @field_validator("monthly_amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        return assert_positive_decimal(v, "monthly_amount")


class UpdateBudgetRequest(BaseModel):
    monthly_amount: Decimal

    @field_validator("monthly_amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        return assert_positive_decimal(v, "monthly_amount")


class BudgetResponse(BaseModel):
    id: UUID
    group_id: UUID
    monthly_amount: float
    year: int
    month: int
    person_id: UUID | None = None

    @classmethod
    def from_domain(cls, budget: CategoryGroupBudget) -> BudgetResponse:
        return cls(
            id=budget.id,
            group_id=budget.group_id,
            monthly_amount=float(budget.monthly_amount),
            year=budget.year,
            month=budget.month,
            person_id=budget.person_id,
        )


class PersonCategorySpend(BaseModel):
    person_id: UUID
    person_name: str
    amount: float


class CategorySpendResponse(BaseModel):
    category: str
    total_amount: float
    transaction_count: int
    include_personal: bool
    household_amount: float
    personal_amounts: list[PersonCategorySpend]


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
    household_spending: float | None = None
    personal_spending: float | None = None


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
        personal_lookup = {cat.name: cat.include_personal for cat in result.categories}
        person_names = {p.id: p.name for p in result.persons}
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
                            include_personal=personal_lookup.get(c.category, False),
                            household_amount=float(c.household_amount),
                            personal_amounts=[
                                PersonCategorySpend(
                                    person_id=pid,
                                    person_name=person_names.get(pid, "Unknown"),
                                    amount=float(amt),
                                )
                                for pid, amt in c.personal_amounts.items()
                            ],
                        )
                        for c in s.categories
                    ],
                    household_spending=float(s.household_spending)
                    if s.household_spending is not None
                    else None,
                    personal_spending=float(s.personal_spending)
                    if s.personal_spending is not None
                    else None,
                )
                for s in overview.group_statuses
            ],
            total_monthly_budget=float(overview.total_monthly_budget),
            total_monthly_spent=float(overview.total_monthly_spent),
            total_ytd_budget=float(overview.total_ytd_budget),
            total_ytd_spent=float(overview.total_ytd_spent),
            budgets=[BudgetResponse.from_domain(b) for b in result.budgets],
        )
