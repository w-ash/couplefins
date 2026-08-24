from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete

from src.domain.entities.settlement_portion import SettlementPortion
from src.infrastructure.persistence.models.settlement_portion_model import (
    SettlementPortionModel,
)
from src.infrastructure.persistence.repositories.base import BaseRepository


class SettlementPortionRepository(
    BaseRepository[SettlementPortion, SettlementPortionModel]
):
    _model_class = SettlementPortionModel

    @staticmethod
    def _to_domain(model: SettlementPortionModel) -> SettlementPortion:
        return SettlementPortion(
            id=UUID(model.id),
            settlement_id=UUID(model.settlement_id),
            year=model.year,
            month=model.month,
            amount=Decimal(model.amount),
        )

    @staticmethod
    def _to_model(entity: SettlementPortion) -> SettlementPortionModel:
        return SettlementPortionModel(
            id=str(entity.id),
            settlement_id=str(entity.settlement_id),
            year=entity.year,
            month=entity.month,
            amount=str(entity.amount),
        )

    async def delete_by_settlement_id(self, settlement_id: UUID) -> int:
        stmt = delete(SettlementPortionModel).where(
            SettlementPortionModel.settlement_id == str(settlement_id)
        )
        return await self._execute_rowcount(stmt)
