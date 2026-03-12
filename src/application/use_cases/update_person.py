from uuid import UUID

import attrs
from attrs import define, field

from src.application.use_cases._shared.command_validators import non_empty_string
from src.domain.entities.person import Person
from src.domain.exceptions import NotFoundError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UpdatePersonCommand:
    id: UUID
    adjustment_account: str = field(validator=non_empty_string)


@define(frozen=True, slots=True)
class UpdatePersonResult:
    person: Person


@define(slots=True)
class UpdatePersonUseCase:
    async def execute(
        self, command: UpdatePersonCommand, uow: UnitOfWorkProtocol
    ) -> UpdatePersonResult:
        async with uow:
            existing = await uow.persons.get_by_id(command.id)
            if existing is None:
                raise NotFoundError(f"Person {command.id} not found")

            updated = attrs.evolve(
                existing, adjustment_account=command.adjustment_account
            )
            saved = await uow.persons.save(updated)
            await uow.commit()
            return UpdatePersonResult(person=saved)
