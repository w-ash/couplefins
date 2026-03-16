from attrs import define

from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetTagsResult:
    tags: list[str]


@define(slots=True)
class GetTagsUseCase:
    async def execute(self, uow: UnitOfWorkProtocol) -> GetTagsResult:
        async with uow:
            tags = await uow.transactions.get_distinct_tags()
            return GetTagsResult(tags=tags)
