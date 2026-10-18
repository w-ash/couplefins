from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from src.domain.entities.co_owned_asset import (
    CONTRIBUTION_KINDS,
    CoOwnedAsset,
    ordered_kinds,
)
from src.domain.literals import parse_literal
from src.infrastructure.persistence.models.co_owned_asset_model import (
    CoOwnedAssetModel,
)
from src.infrastructure.persistence.repositories.base import BaseRepository


class CoOwnedAssetRepository(BaseRepository[CoOwnedAsset, CoOwnedAssetModel]):
    _model_class = CoOwnedAssetModel

    @staticmethod
    def _to_domain(model: CoOwnedAssetModel) -> CoOwnedAsset:
        return CoOwnedAsset(
            id=UUID(model.id),
            name=model.name,
            repair_threshold=Decimal(model.repair_threshold),
            qualifying_kinds=frozenset(
                parse_literal(kind, CONTRIBUTION_KINDS, "contribution kind")
                for kind in model.qualifying_kinds
            ),
            bank_balance=(
                Decimal(model.bank_balance) if model.bank_balance is not None else None
            ),
            bank_balance_as_of=(
                date.fromisoformat(model.bank_balance_as_of)
                if model.bank_balance_as_of
                else None
            ),
            created_at=datetime.fromisoformat(model.created_at),
        )

    @staticmethod
    def _to_model(entity: CoOwnedAsset) -> CoOwnedAssetModel:
        return CoOwnedAssetModel(
            id=str(entity.id),
            name=entity.name,
            repair_threshold=str(entity.repair_threshold),
            # In CONTRIBUTION_KINDS order, so a save writes the same list
            # for the same set.
            qualifying_kinds=ordered_kinds(entity.qualifying_kinds),
            bank_balance=(
                str(entity.bank_balance) if entity.bank_balance is not None else None
            ),
            bank_balance_as_of=(
                entity.bank_balance_as_of.isoformat()
                if entity.bank_balance_as_of
                else None
            ),
            created_at=entity.created_at.isoformat(),
        )

    async def get_current(self) -> CoOwnedAsset | None:
        """The couple's asset: the oldest, as there is one per couple."""
        stmt = select(CoOwnedAssetModel).order_by(CoOwnedAssetModel.created_at).limit(1)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None
