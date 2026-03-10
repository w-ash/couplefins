from datetime import date
from decimal import Decimal
from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class CategoryGroupBudget:
    id: UUID
    group_id: UUID
    monthly_amount: Decimal
    effective_from: date
