from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from src.domain.entities.settlement import Settlement
from src.infrastructure.persistence.models.settlement_model import SettlementModel
from src.infrastructure.persistence.repositories.base import BaseRepository


class SettlementRepository(BaseRepository[Settlement, SettlementModel]):
    _model_class = SettlementModel

    @staticmethod
    def _to_domain(model: SettlementModel) -> Settlement:
        return Settlement(
            id=UUID(model.id),
            year=model.year,
            month=model.month,
            amount=Decimal(model.amount),
            from_person_id=UUID(model.from_person_id),
            to_person_id=UUID(model.to_person_id),
            method=model.method,
            is_waived=model.is_waived,
            notes=model.notes,
            settled_at=datetime.fromisoformat(model.settled_at),
            created_at=datetime.fromisoformat(model.created_at),
        )

    @staticmethod
    def _to_model(entity: Settlement) -> SettlementModel:
        return SettlementModel(
            id=str(entity.id),
            year=entity.year,
            month=entity.month,
            amount=str(entity.amount),
            from_person_id=str(entity.from_person_id),
            to_person_id=str(entity.to_person_id),
            method=entity.method,
            is_waived=entity.is_waived,
            notes=entity.notes,
            settled_at=entity.settled_at.isoformat(),
            created_at=entity.created_at.isoformat(),
        )

    async def get_by_period(self, year: int, month: int) -> list[Settlement]:
        stmt = select(SettlementModel).where(
            SettlementModel.year == year,
            SettlementModel.month == month,
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_by_year(self, year: int) -> list[Settlement]:
        stmt = select(SettlementModel).where(SettlementModel.year == year)
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]
