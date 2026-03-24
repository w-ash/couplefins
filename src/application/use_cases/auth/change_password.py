from collections.abc import Callable
from uuid import UUID

from attrs import define, evolve

from src.domain.auth import validate_password_strength
from src.domain.exceptions import AuthenticationError, NotFoundError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ChangePasswordCommand:
    person_id: UUID
    current_password: str
    new_password: str


@define(frozen=True, slots=True)
class ChangePasswordResult:
    success: bool


@define(slots=True)
class ChangePasswordUseCase:
    verify_password: Callable[[str, str], bool]
    hash_password: Callable[[str], str]

    async def execute(
        self, command: ChangePasswordCommand, uow: UnitOfWorkProtocol
    ) -> ChangePasswordResult:
        async with uow:
            person = await uow.persons.get_by_id(command.person_id)
            if person is None:
                raise NotFoundError("Person not found")

            if not person.password_hash or not self.verify_password(
                command.current_password, person.password_hash
            ):
                raise AuthenticationError("Current password is incorrect")

            validate_password_strength(command.new_password)
            updated = evolve(
                person, password_hash=self.hash_password(command.new_password)
            )
            await uow.persons.save(updated)
            await uow.commit()
            return ChangePasswordResult(success=True)
