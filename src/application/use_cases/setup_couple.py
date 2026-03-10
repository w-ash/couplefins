import uuid

from attrs import define

from src.domain.entities.person import Person
from src.domain.exceptions import DuplicateError, ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class SetupCoupleCommand:
    name1: str
    name2: str


@define(frozen=True, slots=True)
class SetupCoupleResult:
    persons: list[Person]


class SetupCoupleUseCase:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def execute(self, command: SetupCoupleCommand) -> SetupCoupleResult:
        existing = await self._uow.persons.count()
        if existing > 0:
            raise DuplicateError("Couple is already set up")

        if command.name1.strip().lower() == command.name2.strip().lower():
            raise ValidationError("Both names must be different")

        persons = [
            Person(id=uuid.uuid4(), name=command.name1.strip()),
            Person(id=uuid.uuid4(), name=command.name2.strip()),
        ]
        saved = await self._uow.persons.save_batch(persons)
        await self._uow.commit()
        return SetupCoupleResult(persons=saved)
