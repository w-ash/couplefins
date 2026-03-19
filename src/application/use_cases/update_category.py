import attrs
from attrs import define

from src.domain.entities.category import Category
from src.domain.exceptions import NotFoundError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UpdateCategoryCommand:
    name: str
    include_personal: bool


@define(frozen=True, slots=True)
class UpdateCategoryResult:
    category: Category


@define(slots=True)
class UpdateCategoryUseCase:
    async def execute(
        self, command: UpdateCategoryCommand, uow: UnitOfWorkProtocol
    ) -> UpdateCategoryResult:
        async with uow:
            existing = await uow.categories.get_by_name(command.name)
            if existing is None:
                raise NotFoundError(f"Category '{command.name}' not found")

            updated = attrs.evolve(existing, include_personal=command.include_personal)
            saved = await uow.categories.save(updated)
            await uow.commit()
            return UpdateCategoryResult(category=saved)
