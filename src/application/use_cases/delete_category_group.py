from uuid import UUID

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


class DeleteCategoryGroupUseCase:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def execute(self, group_id: UUID) -> None:
        existing = await self._uow.category_groups.get_by_id(group_id)
        if existing is None:
            raise NotFoundError(f"Category group {group_id} not found")

        budgets = await self._uow.category_group_budgets.get_by_group_id(group_id)
        if budgets:
            raise ValidationError(
                f"Cannot delete category group '{existing.name}': "
                f"{len(budgets)} budget(s) reference it"
            )

        await self._uow.category_mappings.delete_by_group_id(group_id)
        await self._uow.category_groups.delete(group_id)
        await self._uow.commit()
