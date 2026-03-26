from collections.abc import Callable
from uuid import UUID

from attrs import define, evolve, field

from src.application.use_cases._shared.command_validators import non_empty_string
from src.domain.auth import validate_password_strength
from src.domain.entities.person import Person
from src.domain.exceptions import AuthenticationError, ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class SetInitialPasswordCommand:
    name: str = field(validator=non_empty_string)
    new_password: str = field(validator=non_empty_string)


@define(frozen=True, slots=True)
class SetInitialPasswordResult:
    person: Person
    token: str


@define(slots=True)
class SetInitialPasswordUseCase:
    hash_password: Callable[[str], str]
    create_token: Callable[[UUID], str]

    async def execute(
        self, command: SetInitialPasswordCommand, uow: UnitOfWorkProtocol
    ) -> SetInitialPasswordResult:
        async with uow:
            person = await uow.persons.get_by_name(command.name)
            if person is None:
                raise AuthenticationError("Person not found")

            if person.password_hash:
                raise ValidationError("Password is already set")

            validate_password_strength(command.new_password)
            updated = evolve(
                person, password_hash=self.hash_password(command.new_password)
            )
            await uow.persons.save(updated)
            await uow.commit()

            token = self.create_token(updated.id)
            return SetInitialPasswordResult(person=updated, token=token)
