from uuid import UUID

from attrs import define

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class DeleteCategoryGroupCommand:
    group_id: UUID
    move_categories_to: UUID | None = None


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

            if command.move_categories_to is not None:
                if command.move_categories_to == command.group_id:
                    raise ValidationError(
                        "Cannot move categories to the same group being deleted"
                    )
                target = await uow.category_groups.get_by_id(command.move_categories_to)
                if target is None:
                    raise NotFoundError(
                        f"Target category group {command.move_categories_to} not found"
                    )
                await uow.categories.remap_by_group_id(
                    command.group_id, command.move_categories_to
                )
            else:
                await uow.categories.unmap_by_group_id(command.group_id)

            await uow.category_group_budgets.delete_by_group_id(command.group_id)
            await uow.category_groups.delete(command.group_id)
            await uow.commit()
            return DeleteCategoryGroupResult()
