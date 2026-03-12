from uuid import UUID

from src.domain.entities.category_group import CategoryGroup
from src.infrastructure.persistence.models.category_group_model import (
    CategoryGroupModel,
)
from src.infrastructure.persistence.repositories.base import BaseRepository


class CategoryGroupRepository(BaseRepository[CategoryGroup, CategoryGroupModel]):
    _model_class = CategoryGroupModel

    @staticmethod
    def _to_domain(model: CategoryGroupModel) -> CategoryGroup:
        return CategoryGroup(
            id=UUID(model.id),
            name=model.name,
        )

    @staticmethod
    def _to_model(entity: CategoryGroup) -> CategoryGroupModel:
        return CategoryGroupModel(
            id=str(entity.id),
            name=entity.name,
        )
