from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class Person:
    id: UUID
    name: str
    adjustment_account: str = ""
    password_hash: str = ""
    theme_preference: str = "system"
    chat_voice: str = "fiona"
