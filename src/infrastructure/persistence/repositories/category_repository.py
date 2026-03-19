from uuid import UUID

from sqlalchemy import CursorResult, select, update as sa_update

from src.domain.entities.category import Category
from src.infrastructure.persistence.models.category_model import CategoryModel
from src.infrastructure.persistence.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category, CategoryModel]):
    _model_class = CategoryModel

    @staticmethod
    def _to_domain(model: CategoryModel) -> Category:
        return Category(
            id=UUID(model.id),
            name=model.name,
            group_id=UUID(model.group_id) if model.group_id else None,
            include_personal=model.include_personal,
        )

    @staticmethod
    def _to_model(entity: Category) -> CategoryModel:
        return CategoryModel(
            id=str(entity.id),
            name=entity.name,
            group_id=str(entity.group_id) if entity.group_id else None,
            include_personal=entity.include_personal,
        )

    async def get_by_name(self, name: str) -> Category | None:
        stmt = select(CategoryModel).where(CategoryModel.name == name)
        result = await self._session.execute(stmt)
        row = result.scalars().first()
        return self._to_domain(row) if row else None

    async def get_by_group_id(self, group_id: UUID) -> list[Category]:
        stmt = select(CategoryModel).where(
            CategoryModel.group_id == str(group_id),
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_unmapped(self) -> list[Category]:
        stmt = select(CategoryModel).where(
            CategoryModel.group_id.is_(None),
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def unmap_by_group_id(self, group_id: UUID) -> int:
        stmt = (
            sa_update(CategoryModel)
            .where(CategoryModel.group_id == str(group_id))
            .values(group_id=None)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        if isinstance(result, CursorResult):
            return result.rowcount
        return 0
