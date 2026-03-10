import uuid

from attrs import define

from src.domain.entities.person import Person
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class CreatePersonCommand:
    name: str
    adjustment_account: str = ""


@define(frozen=True, slots=True)
class CreatePersonResult:
    person: Person


class CreatePersonUseCase:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def execute(self, command: CreatePersonCommand) -> CreatePersonResult:
        person = Person(
            id=uuid.uuid4(),
            name=command.name,
            adjustment_account=command.adjustment_account,
        )
        saved = await self._uow.persons.save(person)
        await self._uow.commit()
        return CreatePersonResult(person=saved)
