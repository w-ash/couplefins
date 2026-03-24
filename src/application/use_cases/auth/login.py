from collections.abc import Callable
from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import non_empty_string
from src.domain.entities.person import Person
from src.domain.exceptions import AuthenticationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

_AUTH_FAILURE = "Invalid name or password"


@define(frozen=True, slots=True)
class LoginCommand:
    name: str = field(validator=non_empty_string)
    password: str = field(validator=non_empty_string)


@define(frozen=True, slots=True)
class LoginResult:
    person: Person
    token: str


@define(slots=True)
class LoginUseCase:
    verify_password: Callable[[str, str], bool]
    create_token: Callable[[UUID], str]

    async def execute(
        self, command: LoginCommand, uow: UnitOfWorkProtocol
    ) -> LoginResult:
        async with uow:
            person = await uow.persons.get_by_name(command.name)
            if person is None or not person.password_hash:
                raise AuthenticationError(_AUTH_FAILURE)

            if not self.verify_password(command.password, person.password_hash):
                raise AuthenticationError(_AUTH_FAILURE)

            token = self.create_token(person.id)
            return LoginResult(person=person, token=token)
