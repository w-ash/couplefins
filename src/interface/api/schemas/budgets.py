from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.application.use_cases._shared.command_validators import assert_positive_decimal
from src.application.use_cases.get_budget_overview import GetBudgetOverviewResult
from src.domain.budget import HealthStatus
from src.domain.categories import CategoryBreakdown
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.interface.api.schemas.reconciliation import MonthReference
from src.interface.api.schemas.types import MoneyField


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


class CopyBudgetsRequest(BaseModel):
    source_year: int = Field(ge=2020, le=2099)
    source_month: int = Field(ge=1, le=12)
    target_year: int = Field(ge=2020, le=2099)
    target_month: int = Field(ge=1, le=12)


class CopyBudgetsResponse(BaseModel):
    copied_count: int
    skipped_count: int


class BudgetResponse(BaseModel):
    id: UUID
    group_id: UUID
    monthly_amount: MoneyField
    year: int
    month: int
    person_id: UUID | None = None

    @classmethod
    def from_domain(cls, budget: CategoryGroupBudget) -> BudgetResponse:
        return cls(
            id=budget.id,
            group_id=budget.group_id,
            monthly_amount=budget.monthly_amount,
            year=budget.year,
            month=budget.month,
            person_id=budget.person_id,
        )


class PersonCategorySpend(BaseModel):
    person_id: UUID
    person_name: str
    amount: MoneyField


class CategorySpendResponse(BaseModel):
    category: str
    total_amount: MoneyField
    transaction_count: int
    include_personal: bool
    household_amount: MoneyField
    personal_amounts: list[PersonCategorySpend]

    @classmethod
    def from_domain_list(
        cls,
        breakdowns: list[CategoryBreakdown],
        personal_lookup: dict[str, bool],
        person_names: dict[UUID, str],
    ) -> list[CategorySpendResponse]:
        return [
            cls(
                category=c.category,
                total_amount=c.total_amount,
                transaction_count=c.transaction_count,
                include_personal=personal_lookup.get(c.category, False),
                household_amount=c.household_amount,
                personal_amounts=[
                    PersonCategorySpend(
                        person_id=pid,
                        person_name=person_names.get(pid, "Unknown"),
                        amount=amt,
                    )
                    for pid, amt in c.personal_amounts.items()
                ],
            )
            for c in breakdowns
        ]


class GroupBudgetStatusResponse(BaseModel):
    # None for the synthetic "Uncategorized" row — spending in categories
    # with no group mapping, surfaced so it doesn't vanish from the totals.
    group_id: UUID | None
    group_name: str
    budget_id: UUID | None
    monthly_budget: MoneyField | None
    monthly_spent: MoneyField
    ytd_budget: MoneyField | None
    ytd_spent: MoneyField
    monthly_health: HealthStatus | None
    ytd_health: HealthStatus | None
    average_monthly_spending: MoneyField
    categories: list[CategorySpendResponse]
    budgeted_months: int
    household_spending: MoneyField | None = None
    personal_spending: MoneyField | None = None
    # Same breakdown as `categories`, computed over the YTD window — the
    # Budget page's YTD-view expansion reads this instead of dividing
    # current-month amounts by a YTD total.
    ytd_categories: list[CategorySpendResponse] = []


class BudgetOverviewResponse(BaseModel):
    year: int
    month: int
    group_statuses: list[GroupBudgetStatusResponse]
    total_monthly_budget: MoneyField
    total_monthly_spent: MoneyField
    total_ytd_budget: MoneyField
    total_ytd_spent: MoneyField
    budgets: list[BudgetResponse]
    spending_drift: MoneyField | None = None
    copyable_source: MonthReference | None = None
    next_month_has_budgets: bool = False
    source_budgets: list[BudgetResponse] = []

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
                    monthly_budget=s.monthly_budget,
                    monthly_spent=s.monthly_spent,
                    ytd_budget=s.ytd_budget,
                    ytd_spent=s.ytd_spent,
                    monthly_health=s.monthly_health,
                    ytd_health=s.ytd_health,
                    average_monthly_spending=s.average_monthly_spending,
                    budgeted_months=s.budgeted_months,
                    categories=CategorySpendResponse.from_domain_list(
                        s.categories, personal_lookup, person_names
                    ),
                    ytd_categories=CategorySpendResponse.from_domain_list(
                        s.ytd_categories, personal_lookup, person_names
                    ),
                    household_spending=s.household_spending,
                    personal_spending=s.personal_spending,
                )
                for s in overview.group_statuses
            ],
            total_monthly_budget=overview.total_monthly_budget,
            total_monthly_spent=overview.total_monthly_spent,
            total_ytd_budget=overview.total_ytd_budget,
            total_ytd_spent=overview.total_ytd_spent,
            budgets=[BudgetResponse.from_domain(b) for b in result.budgets],
            spending_drift=overview.spending_drift,
            copyable_source=MonthReference.from_optional_tuple(result.copyable_source),
            next_month_has_budgets=result.next_month_has_budgets,
            source_budgets=[
                BudgetResponse.from_domain(b) for b in result.source_budgets
            ],
        )
