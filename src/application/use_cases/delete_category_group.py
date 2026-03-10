from uuid import UUID

from attrs import define

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class DeleteCategoryGroupCommand:
    group_id: UUID


@define(frozen=True, slots=True)
class DeleteCategoryGroupResult:
    """Confirms deletion."""


@define(slots=True)
class DeleteCategoryGroupUseCase:
    async def execute(
        self, command: DeleteCategoryGroupCommand, uow: UnitOfWorkProtocol
    ) -> DeleteCategoryGroupResult:
        async with uow:
            existing = await uow.category_groups.get_by_id(command.group_id)
            if existing is None:
                raise NotFoundError(f"Category group {command.group_id} not found")

            budgets = await uow.category_group_budgets.get_by_group_id(command.group_id)
            if budgets:
                raise ValidationError(
                    f"Cannot delete category group '{existing.name}': "
                    f"{len(budgets)} budget(s) reference it"
                )

            await uow.category_mappings.delete_by_group_id(command.group_id)
            await uow.category_groups.delete(command.group_id)
            await uow.commit()
            return DeleteCategoryGroupResult()
