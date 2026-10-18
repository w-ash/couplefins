from attrs import define

from src.application.use_cases._shared.house_records import (
    ObligationTerms,
    build_obligation,
    require_asset,
)
from src.domain.entities.obligation import Obligation
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class CreateObligationCommand:
    terms: ObligationTerms


@define(frozen=True, slots=True)
class CreateObligationResult:
    obligation: Obligation


@define(slots=True)
class CreateObligationUseCase:
    async def execute(
        self, command: CreateObligationCommand, uow: UnitOfWorkProtocol
    ) -> CreateObligationResult:
        """Record a payment that comes due on the couple's home, unpaid.

        Raise ValidationError before the home is set up or when a value is
        rejected, and NotFoundError when its loan does not exist.
        """
        async with uow:
            asset = await require_asset(uow)
            obligation = await build_obligation(uow, None, asset.id, command.terms)
            saved = await uow.obligations.save(obligation)
            await uow.commit()
            return CreateObligationResult(obligation=saved)
