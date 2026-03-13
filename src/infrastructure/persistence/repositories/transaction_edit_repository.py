from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from src.domain.entities.transaction_edit import TransactionEdit
from src.infrastructure.persistence.models.transaction_edit_model import (
    TransactionEditModel,
)
from src.infrastructure.persistence.repositories.base import BaseRepository


class TransactionEditRepository(BaseRepository[TransactionEdit, TransactionEditModel]):
    _model_class = TransactionEditModel

    @staticmethod
    def _to_domain(model: TransactionEditModel) -> TransactionEdit:
        return TransactionEdit(
            id=UUID(model.id),
            transaction_id=UUID(model.transaction_id),
            field_name=model.field_name,
            old_value=model.old_value,
            new_value=model.new_value,
            edited_at=datetime.fromisoformat(model.edited_at),
        )

    @staticmethod
    def _to_model(entity: TransactionEdit) -> TransactionEditModel:
        return TransactionEditModel(
            id=str(entity.id),
            transaction_id=str(entity.transaction_id),
            field_name=entity.field_name,
            old_value=entity.old_value,
            new_value=entity.new_value,
            edited_at=entity.edited_at.isoformat(),
        )

    async def get_by_transaction_id(
        self, transaction_id: UUID
    ) -> list[TransactionEdit]:
        stmt = (
            select(TransactionEditModel)
            .where(TransactionEditModel.transaction_id == str(transaction_id))
            .order_by(TransactionEditModel.edited_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]
