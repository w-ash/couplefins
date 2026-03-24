from collections.abc import Callable
from uuid import UUID

from attrs import define, evolve

from src.domain.auth import validate_password_strength
from src.domain.exceptions import NotFoundError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ResetPartnerPasswordCommand:
    requester_person_id: UUID
    new_password: str


@define(frozen=True, slots=True)
class ResetPartnerPasswordResult:
    success: bool


@define(slots=True)
class ResetPartnerPasswordUseCase:
    hash_password: Callable[[str], str]

    async def execute(
        self, command: ResetPartnerPasswordCommand, uow: UnitOfWorkProtocol
    ) -> ResetPartnerPasswordResult:
        async with uow:
            all_persons = await uow.persons.get_all()
            partner = next(
                (p for p in all_persons if p.id != command.requester_person_id),
                None,
            )
            if partner is None:
                raise NotFoundError("Partner not found")

            validate_password_strength(command.new_password)
            updated = evolve(
                partner, password_hash=self.hash_password(command.new_password)
            )
            await uow.persons.save(updated)
            await uow.commit()
            return ResetPartnerPasswordResult(success=True)
