from uuid import UUID

import attrs
from attrs import define, field

from src.application.use_cases._shared.command_validators import non_empty_string
from src.domain.entities.category_group import CategoryGroup
from src.domain.exceptions import NotFoundError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UpdateCategoryGroupCommand:
    id: UUID
    name: str = field(validator=non_empty_string)
    icon: str | None = None


@define(frozen=True, slots=True)
class UpdateCategoryGroupResult:
    group: CategoryGroup


@define(slots=True)
class UpdateCategoryGroupUseCase:
    async def execute(
        self, command: UpdateCategoryGroupCommand, uow: UnitOfWorkProtocol
    ) -> UpdateCategoryGroupResult:
        async with uow:
            existing = await uow.category_groups.get_by_id(command.id)
            if existing is None:
                raise NotFoundError(f"Category group {command.id} not found")

            updated = attrs.evolve(existing, name=command.name, icon=command.icon)
            saved = await uow.category_groups.save(updated)
            await uow.commit()
            return UpdateCategoryGroupResult(group=saved)
