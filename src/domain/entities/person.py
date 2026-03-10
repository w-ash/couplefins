from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class Person:
    id: UUID
    name: str
    adjustment_account: str = ""
