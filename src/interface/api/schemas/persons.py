from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.domain.entities.person import Person

_NAME_MAX = 50


class SetupCoupleRequest(BaseModel):
    name1: str = Field(max_length=_NAME_MAX)
    name2: str = Field(max_length=_NAME_MAX)

    @field_validator("name1", "name2")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name must not be blank")
        return v


class PersonResponse(BaseModel):
    id: UUID
    name: str
    adjustment_account: str

    @classmethod
    def from_domain(cls, person: Person) -> PersonResponse:
        return cls(
            id=person.id,
            name=person.name,
            adjustment_account=person.adjustment_account,
        )
