from uuid import UUID

from sqlalchemy import select

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
