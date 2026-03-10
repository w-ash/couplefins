from uuid import UUID

from sqlalchemy import CursorResult, delete as sa_delete, select

from src.domain.entities.category_mapping import CategoryMapping
from src.infrastructure.persistence.models.category_mapping_model import (
    CategoryMappingModel,
)
from src.infrastructure.persistence.repositories.base import BaseRepository


class CategoryMappingRepository(BaseRepository[CategoryMapping, CategoryMappingModel]):
    _model_class = CategoryMappingModel

    @staticmethod
    def _to_domain(model: CategoryMappingModel) -> CategoryMapping:
        return CategoryMapping(
            category=model.category,
            group_id=UUID(model.group_id),
        )

    @staticmethod
    def _to_model(entity: CategoryMapping) -> CategoryMappingModel:
        return CategoryMappingModel(
            category=entity.category,
            group_id=str(entity.group_id),
        )

    async def get_by_category(self, category: str) -> CategoryMapping | None:
        result = await self._session.get(CategoryMappingModel, category)
        return self._to_domain(result) if result else None

    async def get_by_group_id(self, group_id: UUID) -> list[CategoryMapping]:
        stmt = select(CategoryMappingModel).where(
            CategoryMappingModel.group_id == str(group_id),
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def delete_by_group_id(self, group_id: UUID) -> int:
        stmt = sa_delete(CategoryMappingModel).where(
            CategoryMappingModel.group_id == str(group_id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        if isinstance(result, CursorResult):
            return result.rowcount
        return 0
