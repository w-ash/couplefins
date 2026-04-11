from uuid import UUID

import attrs
from attrs import define

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.domain.entities.person import Person
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UpdatePersonCommand:
    id: UUID
    adjustment_account: str | None = None
    theme_preference: str | None = None
    chat_voice: str | None = None


@define(frozen=True, slots=True)
class UpdatePersonResult:
    person: Person


@define(slots=True)
class UpdatePersonUseCase:
    async def execute(
        self, command: UpdatePersonCommand, uow: UnitOfWorkProtocol
    ) -> UpdatePersonResult:
        async with uow:
            existing = await require_by_id(uow.persons.get_by_id, command.id, "Person")

            changes: dict[str, str] = {}
            if command.adjustment_account is not None:
                changes["adjustment_account"] = command.adjustment_account
            if command.theme_preference is not None:
                changes["theme_preference"] = command.theme_preference
            if command.chat_voice is not None:
                changes["chat_voice"] = command.chat_voice

            if not changes:
                return UpdatePersonResult(person=existing)

            updated = attrs.evolve(existing, **changes)
            saved = await uow.persons.save(updated)
            await uow.commit()
            return UpdatePersonResult(person=saved)
