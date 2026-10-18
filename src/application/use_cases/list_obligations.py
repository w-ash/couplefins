from attrs import define

from src.domain.entities.obligation import Obligation
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ListObligationsCommand:
    """Parameterless — exists for API uniformity."""


@define(frozen=True, slots=True)
class ListObligationsResult:
    obligations: list[Obligation]  # paid or not, in due order


@define(slots=True)
class ListObligationsUseCase:
    async def execute(
        self, _command: ListObligationsCommand, uow: UnitOfWorkProtocol
    ) -> ListObligationsResult:
        """Every obligation of the couple's home; none before the home is
        set up."""
        async with uow:
            asset = await uow.co_owned_assets.get_current()
            obligations = (
                await uow.obligations.get_by_asset_id(asset.id) if asset else []
            )
            return ListObligationsResult(obligations=obligations)
