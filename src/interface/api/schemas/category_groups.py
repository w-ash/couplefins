from uuid import UUID

from pydantic import BaseModel

from src.application.use_cases.list_category_groups import CategoryGroupWithMappings
from src.domain.entities.category_group import CategoryGroup


class CreateCategoryGroupRequest(BaseModel):
    name: str
    icon: str | None = None


class UpdateCategoryGroupRequest(BaseModel):
    name: str
    icon: str | None = None


class MappingEntryRequest(BaseModel):
    category: str
    group_id: UUID


class BulkUpdateMappingsRequest(BaseModel):
    mappings: list[MappingEntryRequest]


class CategoryGroupResponse(BaseModel):
    id: UUID
    name: str
    icon: str | None
    categories: list[str]

    @classmethod
    def from_domain(cls, item: CategoryGroupWithMappings) -> CategoryGroupResponse:
        return cls(
            id=item.group.id,
            name=item.group.name,
            icon=item.group.icon,
            categories=sorted(m.category for m in item.mappings),
        )

    @classmethod
    def from_group(cls, group: CategoryGroup) -> CategoryGroupResponse:
        return cls(id=group.id, name=group.name, icon=group.icon, categories=[])
