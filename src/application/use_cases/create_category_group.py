import uuid

from attrs import define, field

from src.application.use_cases._shared.command_validators import non_empty_string
from src.domain.entities.category_group import CategoryGroup
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class CreateCategoryGroupCommand:
    name: str = field(validator=non_empty_string)
    icon: str | None = None


@define(frozen=True, slots=True)
class CreateCategoryGroupResult:
    group: CategoryGroup


@define(slots=True)
class CreateCategoryGroupUseCase:
    async def execute(
        self, command: CreateCategoryGroupCommand, uow: UnitOfWorkProtocol
    ) -> CreateCategoryGroupResult:
        async with uow:
            group = CategoryGroup(id=uuid.uuid4(), name=command.name, icon=command.icon)
            saved = await uow.category_groups.save(group)
            await uow.commit()
            return CreateCategoryGroupResult(group=saved)
