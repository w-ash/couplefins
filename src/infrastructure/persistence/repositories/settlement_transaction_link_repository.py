from uuid import UUID

from sqlalchemy import delete, select

from src.domain.entities.settlement_transaction_link import SettlementTransactionLink
from src.infrastructure.persistence.models.settlement_transaction_link_model import (
    SettlementTransactionLinkModel,
)
from src.infrastructure.persistence.repositories.base import BaseRepository


class SettlementTransactionLinkRepository(
    BaseRepository[SettlementTransactionLink, SettlementTransactionLinkModel]
):
    _model_class = SettlementTransactionLinkModel

    @staticmethod
    def _to_domain(model: SettlementTransactionLinkModel) -> SettlementTransactionLink:
        return SettlementTransactionLink(
            id=UUID(model.id),
            settlement_id=UUID(model.settlement_id),
            transaction_id=UUID(model.transaction_id),
        )

    @staticmethod
    def _to_model(entity: SettlementTransactionLink) -> SettlementTransactionLinkModel:
        return SettlementTransactionLinkModel(
            id=str(entity.id),
            settlement_id=str(entity.settlement_id),
            transaction_id=str(entity.transaction_id),
        )

    async def get_by_settlement_ids(
        self, settlement_ids: list[UUID]
    ) -> list[SettlementTransactionLink]:
        if not settlement_ids:
            return []
        stmt = select(SettlementTransactionLinkModel).where(
            SettlementTransactionLinkModel.settlement_id.in_(  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                [str(sid) for sid in settlement_ids]
            ),
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_by_transaction_id(
        self, transaction_id: UUID
    ) -> list[SettlementTransactionLink]:
        stmt = select(SettlementTransactionLinkModel).where(
            SettlementTransactionLinkModel.transaction_id == str(transaction_id),
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def delete_by_settlement_id(self, settlement_id: UUID) -> int:
        stmt = delete(SettlementTransactionLinkModel).where(
            SettlementTransactionLinkModel.settlement_id == str(settlement_id)
        )
        return await self._execute_rowcount(stmt)

    async def delete_by_transaction_id(self, transaction_id: UUID) -> int:
        stmt = delete(SettlementTransactionLinkModel).where(
            SettlementTransactionLinkModel.transaction_id == str(transaction_id)
        )
        return await self._execute_rowcount(stmt)

    async def delete_by_settlement_and_transaction(
        self, settlement_id: UUID, transaction_id: UUID
    ) -> int:
        stmt = delete(SettlementTransactionLinkModel).where(
            SettlementTransactionLinkModel.settlement_id == str(settlement_id),
            SettlementTransactionLinkModel.transaction_id == str(transaction_id),
        )
        return await self._execute_rowcount(stmt)
