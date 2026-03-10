from uuid import UUID

from pydantic import BaseModel

from src.domain.entities.person import Person


class CreatePersonRequest(BaseModel):
    name: str
    adjustment_account: str = ""


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
