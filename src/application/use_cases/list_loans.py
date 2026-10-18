from attrs import define

from src.domain.entities.loan import Loan
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ListLoansCommand:
    """Parameterless — exists for API uniformity."""


@define(frozen=True, slots=True)
class ListLoansResult:
    loans: list[Loan]  # open and closed, in the order they were created


@define(slots=True)
class ListLoansUseCase:
    async def execute(
        self, _command: ListLoansCommand, uow: UnitOfWorkProtocol
    ) -> ListLoansResult:
        """Every loan on the couple's home; none before the home is set up."""
        async with uow:
            asset = await uow.co_owned_assets.get_current()
            loans = await uow.loans.get_by_asset_id(asset.id) if asset else []
            return ListLoansResult(loans=loans)
