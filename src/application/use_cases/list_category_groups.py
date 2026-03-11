from uuid import UUID

from attrs import define

from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.category_mapping import CategoryMapping
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ListCategoryGroupsCommand:
    """Parameterless — exists for API uniformity."""


@define(frozen=True, slots=True)
class CategoryGroupWithMappings:
    group: CategoryGroup
    mappings: list[CategoryMapping]


@define(frozen=True, slots=True)
class ListCategoryGroupsResult:
    items: list[CategoryGroupWithMappings]


@define(slots=True)
class ListCategoryGroupsUseCase:
    async def execute(
        self, _command: ListCategoryGroupsCommand, uow: UnitOfWorkProtocol
    ) -> ListCategoryGroupsResult:
        async with uow:
            groups = await uow.category_groups.get_all()
            all_mappings = await uow.category_mappings.get_all()

            mappings_by_group: dict[UUID, list[CategoryMapping]] = {}
            for mapping in all_mappings:
                if mapping.group_id is not None:
                    mappings_by_group.setdefault(mapping.group_id, []).append(mapping)

            items = [
                CategoryGroupWithMappings(
                    group=group,
                    mappings=mappings_by_group.get(group.id, []),
                )
                for group in groups
            ]
            return ListCategoryGroupsResult(items=items)


async def list_category_groups(
    uow: UnitOfWorkProtocol,
) -> ListCategoryGroupsResult:
    return await ListCategoryGroupsUseCase().execute(ListCategoryGroupsCommand(), uow)
