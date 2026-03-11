from abc import abstractmethod
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.models.base import Base


def date_month_prefix(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}-"


class BaseRepository[TEntity, TModel: Base]:
    _model_class: type[TModel]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    @abstractmethod
    def _to_domain(model: TModel) -> TEntity: ...

    @staticmethod
    @abstractmethod
    def _to_model(entity: TEntity) -> TModel: ...

    async def get_by_id(self, id: UUID) -> TEntity | None:
        result = await self._session.get(self._model_class, str(id))
        return self._to_domain(result) if result else None

    async def get_all(self) -> list[TEntity]:
        result = await self._session.execute(select(self._model_class))
        return [self._to_domain(row) for row in result.scalars().all()]

    async def save(self, entity: TEntity) -> TEntity:
        model = self._to_model(entity)
        merged = await self._session.merge(model)
        await self._session.flush()
        return self._to_domain(merged)

    async def save_batch(self, entities: list[TEntity]) -> list[TEntity]:
        models = [self._to_model(e) for e in entities]
        merged = [await self._session.merge(m) for m in models]
        await self._session.flush()
        return [self._to_domain(m) for m in merged]

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(self._model_class)
        )
        return result.scalar_one()
