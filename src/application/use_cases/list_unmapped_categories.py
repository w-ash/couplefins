from attrs import define

from src.application.use_cases._shared.transactions import find_unmapped_categories
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
            tx_categories = await uow.transactions.get_distinct_categories()
            all_mappings = await uow.category_mappings.get_all()
            unmapped = find_unmapped_categories(all_mappings, set(tx_categories))
            return ListUnmappedCategoriesResult(categories=unmapped)


async def list_unmapped_categories(
    uow: UnitOfWorkProtocol,
) -> ListUnmappedCategoriesResult:
    return await ListUnmappedCategoriesUseCase().execute(
        ListUnmappedCategoriesCommand(), uow
    )
