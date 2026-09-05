from uuid import UUID

from pydantic import BaseModel

from src.application.use_cases.list_category_groups import CategoryGroupWithCategories
from src.domain.entities.category import Category
from src.domain.entities.category_group import CategoryGroup, GroupKind


class CreateCategoryGroupRequest(BaseModel):
    name: str
    icon: str | None = None
    kind: GroupKind = "expense"


class UpdateCategoryGroupRequest(BaseModel):
    name: str
    kind: GroupKind
    icon: str | None = None


class MappingEntryRequest(BaseModel):
    category: str
    group_id: UUID


class BulkUpdateMappingsRequest(BaseModel):
    mappings: list[MappingEntryRequest]


class UpdateCategoryRequest(BaseModel):
    include_personal: bool


class CategoryResponse(BaseModel):
    name: str
    include_personal: bool

    @classmethod
    def from_domain(cls, category: Category) -> CategoryResponse:
        return cls(name=category.name, include_personal=category.include_personal)


class CategoryGroupResponse(BaseModel):
    id: UUID
    name: str
    icon: str | None
    kind: GroupKind
    categories: list[CategoryResponse]

    @classmethod
    def from_domain(cls, item: CategoryGroupWithCategories) -> CategoryGroupResponse:
        return cls(
            id=item.group.id,
            name=item.group.name,
            icon=item.group.icon,
            kind=item.group.kind,
            categories=sorted(
                [CategoryResponse.from_domain(c) for c in item.categories],
                key=lambda c: c.name,
            ),
        )

    @classmethod
    def from_group(cls, group: CategoryGroup) -> CategoryGroupResponse:
        return cls(
            id=group.id,
            name=group.name,
            icon=group.icon,
            kind=group.kind,
            categories=[],
        )
