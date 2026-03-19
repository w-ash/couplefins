from uuid import UUID

from attrs import define

from src.domain.entities.category import Category
from src.domain.entities.category_group import CategoryGroup
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ListCategoryGroupsCommand:
    """Parameterless — exists for API uniformity."""


@define(frozen=True, slots=True)
class CategoryGroupWithCategories:
    group: CategoryGroup
    categories: list[Category]


@define(frozen=True, slots=True)
class ListCategoryGroupsResult:
    items: list[CategoryGroupWithCategories]


@define(slots=True)
class ListCategoryGroupsUseCase:
    async def execute(
        self, _command: ListCategoryGroupsCommand, uow: UnitOfWorkProtocol
    ) -> ListCategoryGroupsResult:
        async with uow:
            groups = await uow.category_groups.get_all()
            all_categories = await uow.categories.get_all()

            cats_by_group: dict[UUID, list[Category]] = {}
            for cat in all_categories:
                if cat.group_id is not None:
                    cats_by_group.setdefault(cat.group_id, []).append(cat)

            items = [
                CategoryGroupWithCategories(
                    group=group,
                    categories=cats_by_group.get(group.id, []),
                )
                for group in groups
            ]
            return ListCategoryGroupsResult(items=items)


async def list_category_groups(
    uow: UnitOfWorkProtocol,
) -> ListCategoryGroupsResult:
    return await ListCategoryGroupsUseCase().execute(ListCategoryGroupsCommand(), uow)
