from datetime import UTC, date, datetime
from decimal import Decimal
import uuid

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    as_validation_error,
    non_empty,
    quantize_cents,
)
from src.domain.entities.co_owned_asset import ContributionKind, CoOwnedAsset
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


def _optional_cents(value: Decimal | None) -> Decimal | None:
    return None if value is None else quantize_cents(value)


@define(frozen=True, slots=True)
class SaveCoOwnedAssetCommand:
    """The whole asset: a save replaces every setting.

    The bank balance and its date are both given or both None.
    """

    name: str = field(validator=non_empty)
    repair_threshold: Decimal = field(converter=quantize_cents)
    qualifying_kinds: frozenset[ContributionKind]
    bank_balance: Decimal | None = field(default=None, converter=_optional_cents)
    bank_balance_as_of: date | None = None

    def __attrs_post_init__(self) -> None:
        if (self.bank_balance is None) != (self.bank_balance_as_of is None):
            raise ValueError(
                "bank_balance and bank_balance_as_of must be given together"
            )


@define(frozen=True, slots=True)
class SaveCoOwnedAssetResult:
    asset: CoOwnedAsset


@define(slots=True)
class SaveCoOwnedAssetUseCase:
    async def execute(
        self, command: SaveCoOwnedAssetCommand, uow: UnitOfWorkProtocol
    ) -> SaveCoOwnedAssetResult:
        """Create the couple's asset, or update it: there is one per couple.

        An update keeps the asset's id and creation time. Raise
        ValidationError when the repair threshold is negative.
        """
        async with uow:
            current = await uow.co_owned_assets.get_current()
            asset = as_validation_error(
                CoOwnedAsset,
                id=current.id if current else uuid.uuid4(),
                name=command.name,
                repair_threshold=command.repair_threshold,
                qualifying_kinds=command.qualifying_kinds,
                bank_balance=command.bank_balance,
                bank_balance_as_of=command.bank_balance_as_of,
                created_at=current.created_at if current else datetime.now(UTC),
            )
            saved = await uow.co_owned_assets.save(asset)
            await uow.commit()
            return SaveCoOwnedAssetResult(asset=saved)
