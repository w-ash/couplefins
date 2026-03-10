import uuid

from attrs import define, field

from src.application.use_cases._shared.command_validators import non_empty_string
from src.domain.entities.person import Person
from src.domain.exceptions import DuplicateError, ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class SetupCoupleCommand:
    name1: str = field(validator=non_empty_string)
    name2: str = field(validator=non_empty_string)


@define(frozen=True, slots=True)
class SetupCoupleResult:
    persons: list[Person]


@define(slots=True)
class SetupCoupleUseCase:
    async def execute(
        self, command: SetupCoupleCommand, uow: UnitOfWorkProtocol
    ) -> SetupCoupleResult:
        async with uow:
            existing = await uow.persons.count()
            if existing > 0:
                raise DuplicateError("Couple is already set up")

            if command.name1.strip().lower() == command.name2.strip().lower():
                raise ValidationError("Both names must be different")

            persons = [
                Person(id=uuid.uuid4(), name=command.name1.strip()),
                Person(id=uuid.uuid4(), name=command.name2.strip()),
            ]
            saved = await uow.persons.save_batch(persons)
            await uow.commit()
            return SetupCoupleResult(persons=saved)
