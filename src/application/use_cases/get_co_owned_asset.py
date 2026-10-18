from attrs import define

from src.domain.entities.co_owned_asset import CoOwnedAsset
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetCoOwnedAssetCommand:
    """Parameterless — exists for API uniformity."""


@define(frozen=True, slots=True)
class GetCoOwnedAssetResult:
    """The couple's home and its share settings, or None before setup."""

    asset: CoOwnedAsset | None


@define(slots=True)
class GetCoOwnedAssetUseCase:
    async def execute(
        self, _command: GetCoOwnedAssetCommand, uow: UnitOfWorkProtocol
    ) -> GetCoOwnedAssetResult:
        async with uow:
            return GetCoOwnedAssetResult(asset=await uow.co_owned_assets.get_current())
