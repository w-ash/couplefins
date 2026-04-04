from uuid import UUID

from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.exceptions import ForbiddenError


def require_budget_ownership(budget: CategoryGroupBudget, actor_id: UUID) -> None:
    """Raise ForbiddenError if actor doesn't own a personal budget."""
    if budget.person_id is not None and budget.person_id != actor_id:
        raise ForbiddenError("Cannot modify another person's budget")
