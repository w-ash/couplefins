import uuid

from attrs import define

from src.domain.entities.category_group import CategoryGroup
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class CreateCategoryGroupCommand:
    name: str


class CreateCategoryGroupUseCase:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def execute(self, command: CreateCategoryGroupCommand) -> CategoryGroup:
        group = CategoryGroup(id=uuid.uuid4(), name=command.name)
        saved = await self._uow.category_groups.save(group)
        await self._uow.commit()
        return saved
