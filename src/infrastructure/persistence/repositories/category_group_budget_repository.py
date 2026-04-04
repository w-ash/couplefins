from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, delete as sa_delete, select

from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.infrastructure.persistence.models.category_group_budget_model import (
    CategoryGroupBudgetModel,
)
from src.infrastructure.persistence.repositories.base import BaseRepository


class CategoryGroupBudgetRepository(
    BaseRepository[CategoryGroupBudget, CategoryGroupBudgetModel]
):
    _model_class = CategoryGroupBudgetModel

    @staticmethod
    def _to_domain(model: CategoryGroupBudgetModel) -> CategoryGroupBudget:
        return CategoryGroupBudget(
            id=UUID(model.id),
            group_id=UUID(model.group_id),
            monthly_amount=Decimal(model.monthly_amount),
            year=model.year,
            month=model.month,
            person_id=UUID(model.person_id) if model.person_id else None,
        )

    @staticmethod
    def _to_model(entity: CategoryGroupBudget) -> CategoryGroupBudgetModel:
        return CategoryGroupBudgetModel(
            id=str(entity.id),
            group_id=str(entity.group_id),
            monthly_amount=str(entity.monthly_amount),
            year=entity.year,
            month=entity.month,
            person_id=str(entity.person_id) if entity.person_id else None,
        )

    @staticmethod
    def _person_filter(
        stmt: Select[tuple[CategoryGroupBudgetModel]], person_id: UUID | None
    ) -> Select[tuple[CategoryGroupBudgetModel]]:
        if person_id is None:
            return stmt.where(CategoryGroupBudgetModel.person_id.is_(None))
        return stmt.where(CategoryGroupBudgetModel.person_id == str(person_id))

    async def get_by_month(
        self, year: int, month: int, person_id: UUID | None
    ) -> list[CategoryGroupBudget]:
        stmt = select(CategoryGroupBudgetModel).where(
            CategoryGroupBudgetModel.year == year,
            CategoryGroupBudgetModel.month == month,
        )
        stmt = self._person_filter(stmt, person_id)
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_by_year(
        self, year: int, person_id: UUID | None
    ) -> list[CategoryGroupBudget]:
        stmt = select(CategoryGroupBudgetModel).where(
            CategoryGroupBudgetModel.year == year,
        )
        stmt = self._person_filter(stmt, person_id)
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def delete_by_group_id(self, group_id: UUID) -> int:
        stmt = sa_delete(CategoryGroupBudgetModel).where(
            CategoryGroupBudgetModel.group_id == str(group_id),
        )
        return await self._execute_rowcount(stmt)
