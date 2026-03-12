from attrs import define

from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ListBudgetsResult:
    budgets: list[CategoryGroupBudget]


async def list_budgets(uow: UnitOfWorkProtocol) -> ListBudgetsResult:
    async with uow:
        budgets = await uow.category_group_budgets.get_all()
        return ListBudgetsResult(budgets=budgets)
