from attrs import define

from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ListUnmappedCategoriesCommand:
    """Parameterless — exists for API uniformity."""


@define(frozen=True, slots=True)
class ListUnmappedCategoriesResult:
    categories: list[str]


@define(slots=True)
class ListUnmappedCategoriesUseCase:
    async def execute(
        self, _command: ListUnmappedCategoriesCommand, uow: UnitOfWorkProtocol
    ) -> ListUnmappedCategoriesResult:
        async with uow:
            unmapped = await uow.category_mappings.get_unmapped()
            return ListUnmappedCategoriesResult(
                categories=sorted(m.category for m in unmapped)
            )


async def list_unmapped_categories(
    uow: UnitOfWorkProtocol,
) -> ListUnmappedCategoriesResult:
    return await ListUnmappedCategoriesUseCase().execute(
        ListUnmappedCategoriesCommand(), uow
    )
