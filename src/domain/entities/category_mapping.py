from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class CategoryMapping:
    category: str
    group_id: UUID
