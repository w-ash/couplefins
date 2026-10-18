from uuid import UUID

from attrs import define

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.house_records import (
    ObligationTerms,
    build_obligation,
)
from src.domain.entities.obligation import Obligation
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UpdateObligationCommand:
    obligation_id: UUID
    terms: ObligationTerms


@define(frozen=True, slots=True)
class UpdateObligationResult:
    obligation: Obligation


@define(slots=True)
class UpdateObligationUseCase:
    async def execute(
        self, command: UpdateObligationCommand, uow: UnitOfWorkProtocol
    ) -> UpdateObligationResult:
        """Replace every value of an obligation but the row that paid it, as
        when the bill replaces an estimate.

        Raise NotFoundError when the obligation or its loan does not exist,
        and ValidationError when a value is rejected.
        """
        async with uow:
            current = await require_by_id(
                uow.obligations.get_by_id, command.obligation_id, "Obligation"
            )
            obligation = await build_obligation(
                uow, current, current.asset_id, command.terms
            )
            saved = await uow.obligations.save(obligation)
            await uow.commit()
            return UpdateObligationResult(obligation=saved)
