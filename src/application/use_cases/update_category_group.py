from uuid import UUID

from attrs import define

from src.domain.entities.category_group import CategoryGroup
from src.domain.exceptions import NotFoundError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UpdateCategoryGroupCommand:
    id: UUID
    name: str


class UpdateCategoryGroupUseCase:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def execute(self, command: UpdateCategoryGroupCommand) -> CategoryGroup:
        existing = await self._uow.category_groups.get_by_id(command.id)
        if existing is None:
            raise NotFoundError(f"Category group {command.id} not found")

        updated = CategoryGroup(id=existing.id, name=command.name)
        saved = await self._uow.category_groups.save(updated)
        await self._uow.commit()
        return saved
