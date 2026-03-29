from uuid import UUID

from attrs import define

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.domain.exceptions import ValidationError
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
            await require_by_id(
                uow.category_groups.get_by_id, command.group_id, "Category group"
            )

            if command.move_categories_to is not None:
                if command.move_categories_to == command.group_id:
                    raise ValidationError(
                        "Cannot move categories to the same group being deleted"
                    )
                await require_by_id(
                    uow.category_groups.get_by_id,
                    command.move_categories_to,
                    "Target category group",
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
