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
            unmapped = await uow.categories.get_unmapped()
            return ListUnmappedCategoriesResult(
                categories=sorted(c.name for c in unmapped)
            )


async def list_unmapped_categories(
    uow: UnitOfWorkProtocol,
) -> ListUnmappedCategoriesResult:
    return await ListUnmappedCategoriesUseCase().execute(
        ListUnmappedCategoriesCommand(), uow
    )
