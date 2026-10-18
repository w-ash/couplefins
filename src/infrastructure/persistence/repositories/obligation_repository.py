from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.sql.expression import ColumnElement

from src.domain.entities.obligation import OBLIGATION_KINDS, Obligation
from src.domain.literals import parse_literal
from src.infrastructure.persistence.models.obligation_model import ObligationModel
from src.infrastructure.persistence.repositories.base import (
    BaseRepository,
    optional_str,
    optional_uuid,
)


class ObligationRepository(BaseRepository[Obligation, ObligationModel]):
    _model_class = ObligationModel

    @staticmethod
    def _to_domain(model: ObligationModel) -> Obligation:
        return Obligation(
            id=UUID(model.id),
            asset_id=UUID(model.asset_id),
            kind=parse_literal(model.kind, OBLIGATION_KINDS, "obligation kind"),
            description=model.description,
            amount=Decimal(model.amount),
            is_estimate=model.is_estimate,
            due_on=date.fromisoformat(model.due_on),
            late_after=(
                date.fromisoformat(model.late_after) if model.late_after else None
            ),
            pays_from=model.pays_from,
            loan_id=optional_uuid(model.loan_id),
            paid_by_transaction_id=optional_uuid(model.paid_by_transaction_id),
            notes=model.notes,
        )

    @staticmethod
    def _to_model(entity: Obligation) -> ObligationModel:
        return ObligationModel(
            id=str(entity.id),
            asset_id=str(entity.asset_id),
            kind=entity.kind,
            description=entity.description,
            amount=str(entity.amount),
            is_estimate=entity.is_estimate,
            due_on=entity.due_on.isoformat(),
            late_after=entity.late_after.isoformat() if entity.late_after else None,
            pays_from=entity.pays_from,
            loan_id=optional_str(entity.loan_id),
            paid_by_transaction_id=optional_str(entity.paid_by_transaction_id),
            notes=entity.notes,
        )

    async def _in_due_order(self, condition: ColumnElement[bool]) -> list[Obligation]:
        stmt = (
            select(ObligationModel)
            .where(condition)
            .order_by(ObligationModel.due_on, ObligationModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_by_asset_id(self, asset_id: UUID) -> list[Obligation]:
        """The asset's obligations, paid or not, in due order."""
        return await self._in_due_order(ObligationModel.asset_id == str(asset_id))

    async def get_by_loan_id(self, loan_id: UUID) -> list[Obligation]:
        """The loan's obligations, paid or not, in due order."""
        return await self._in_due_order(ObligationModel.loan_id == str(loan_id))

    async def get_by_paid_transaction_ids(
        self, transaction_ids: list[UUID]
    ) -> list[Obligation]:
        """The obligations that the given rows pay, in due order."""
        if not transaction_ids:
            return []
        return await self._in_due_order(
            ObligationModel.paid_by_transaction_id.in_([
                str(i) for i in transaction_ids
            ])
        )

    async def delete_by_ids(self, ids: list[UUID]) -> int:
        if not ids:
            return 0
        stmt = delete(ObligationModel).where(
            ObligationModel.id.in_([str(i) for i in ids])
        )
        return await self._execute_rowcount(stmt)
