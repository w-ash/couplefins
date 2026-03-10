from uuid import UUID

from attrs import define

from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.category_mapping import CategoryMapping
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class CategoryGroupWithMappings:
    group: CategoryGroup
    mappings: list[CategoryMapping]


class ListCategoryGroupsUseCase:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def execute(self) -> list[CategoryGroupWithMappings]:
        groups = await self._uow.category_groups.get_all()
        all_mappings = await self._uow.category_mappings.get_all()

        mappings_by_group: dict[UUID, list[CategoryMapping]] = {}
        for mapping in all_mappings:
            mappings_by_group.setdefault(mapping.group_id, []).append(mapping)

        return [
            CategoryGroupWithMappings(
                group=group,
                mappings=mappings_by_group.get(group.id, []),
            )
            for group in groups
        ]


async def list_category_groups(
    uow: UnitOfWorkProtocol,
) -> list[CategoryGroupWithMappings]:
    return await ListCategoryGroupsUseCase(uow).execute()
