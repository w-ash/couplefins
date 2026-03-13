from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class CategoryGroup:
    id: UUID
    name: str
    icon: str | None = None
