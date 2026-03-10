from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


class ListUnmappedCategoriesUseCase:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def execute(self) -> list[str]:
        tx_categories = await self._uow.transactions.get_distinct_categories()
        all_mappings = await self._uow.category_mappings.get_all()
        mapped_categories = {m.category for m in all_mappings}
        unmapped = sorted(set(tx_categories) - mapped_categories)
        return unmapped


async def list_unmapped_categories(uow: UnitOfWorkProtocol) -> list[str]:
    return await ListUnmappedCategoriesUseCase(uow).execute()
