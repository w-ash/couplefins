from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from src.domain.entities.reconciliation_period import ReconciliationPeriod
from src.infrastructure.persistence.models.reconciliation_period_model import (
    ReconciliationPeriodModel,
)
from src.infrastructure.persistence.repositories.base import BaseRepository


class ReconciliationPeriodRepository(
    BaseRepository[ReconciliationPeriod, ReconciliationPeriodModel]
):
    _model_class = ReconciliationPeriodModel

    @staticmethod
    def _to_domain(model: ReconciliationPeriodModel) -> ReconciliationPeriod:
        return ReconciliationPeriod(
            id=UUID(model.id),
            year=model.year,
            month=model.month,
            is_finalized=model.is_finalized,
            finalized_at=datetime.fromisoformat(model.finalized_at)
            if model.finalized_at
            else None,
            notes=model.notes,
            created_at=datetime.fromisoformat(model.created_at),
        )

    @staticmethod
    def _to_model(entity: ReconciliationPeriod) -> ReconciliationPeriodModel:
        return ReconciliationPeriodModel(
            id=str(entity.id),
            year=entity.year,
            month=entity.month,
            is_finalized=entity.is_finalized,
            finalized_at=entity.finalized_at.isoformat()
            if entity.finalized_at
            else None,
            notes=entity.notes,
            created_at=entity.created_at.isoformat(),
        )

    async def get_by_period(self, year: int, month: int) -> ReconciliationPeriod | None:
        stmt = select(ReconciliationPeriodModel).where(
            ReconciliationPeriodModel.year == year,
            ReconciliationPeriodModel.month == month,
        )
        result = await self._session.execute(stmt)
        model = result.scalars().first()
        return self._to_domain(model) if model else None
