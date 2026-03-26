from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete as sa_delete, select

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
            effective_from=date.fromisoformat(model.effective_from),
            person_id=UUID(model.person_id) if model.person_id else None,
        )

    @staticmethod
    def _to_model(entity: CategoryGroupBudget) -> CategoryGroupBudgetModel:
        return CategoryGroupBudgetModel(
            id=str(entity.id),
            group_id=str(entity.group_id),
            monthly_amount=str(entity.monthly_amount),
            effective_from=entity.effective_from.isoformat(),
            person_id=str(entity.person_id) if entity.person_id else None,
        )

    async def get_by_person(self, person_id: UUID | None) -> list[CategoryGroupBudget]:
        if person_id is None:
            stmt = select(CategoryGroupBudgetModel).where(
                CategoryGroupBudgetModel.person_id.is_(None)
            )
        else:
            stmt = select(CategoryGroupBudgetModel).where(
                CategoryGroupBudgetModel.person_id == str(person_id)
            )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def delete_by_group_id(self, group_id: UUID) -> int:
        stmt = sa_delete(CategoryGroupBudgetModel).where(
            CategoryGroupBudgetModel.group_id == str(group_id),
        )
        return await self._execute_rowcount(stmt)
