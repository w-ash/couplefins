from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class Category:
    id: UUID
    name: str
    group_id: UUID | None
    include_personal: bool = False
