from uuid import UUID

from attrs import define

from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ListBudgetsResult:
    budgets: list[CategoryGroupBudget]


async def list_budgets(uow: UnitOfWorkProtocol, person_id: UUID) -> ListBudgetsResult:
    async with uow:
        all_budgets = await uow.category_group_budgets.get_all()
        scoped = [
            b for b in all_budgets if b.person_id is None or b.person_id == person_id
        ]
        return ListBudgetsResult(budgets=scoped)
