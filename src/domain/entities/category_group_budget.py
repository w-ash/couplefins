from decimal import Decimal
from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class CategoryGroupBudget:
    id: UUID
    group_id: UUID
    monthly_amount: Decimal
    year: int
    month: int
    person_id: UUID | None = None
