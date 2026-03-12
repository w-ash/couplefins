from datetime import date
from decimal import Decimal
import json
from uuid import UUID

from sqlalchemy import CursorResult, delete, select, update

from src.domain.entities.transaction import Transaction
from src.infrastructure.persistence.models.transaction_model import TransactionModel
from src.infrastructure.persistence.repositories.base import (
    BaseRepository,
    date_month_prefix,
)


class TransactionRepository(BaseRepository[Transaction, TransactionModel]):
    _model_class = TransactionModel

    @staticmethod
    def _to_domain(model: TransactionModel) -> Transaction:
        return Transaction(
            id=UUID(model.id),
            upload_id=UUID(model.upload_id),
            date=date.fromisoformat(model.date),
            merchant=model.merchant,
            category=model.category,
            account=model.account,
            original_statement=model.original_statement,
            occurrence=model.occurrence,
            notes=model.notes,
            amount=Decimal(model.amount),
            tags=tuple(json.loads(model.tags_json)),
            payer_person_id=UUID(model.payer_person_id),
            payer_percentage=model.payer_percentage,
        )

    @staticmethod
    def _to_model(entity: Transaction) -> TransactionModel:
        return TransactionModel(
            id=str(entity.id),
            upload_id=str(entity.upload_id),
            date=entity.date.isoformat(),
            merchant=entity.merchant,
            category=entity.category,
            account=entity.account,
            original_statement=entity.original_statement,
            occurrence=entity.occurrence,
            notes=entity.notes,
            amount=str(entity.amount),
            tags_json=json.dumps(list(entity.tags)),
            is_shared=entity.is_shared,
            payer_person_id=str(entity.payer_person_id),
            payer_percentage=entity.payer_percentage,
        )

    async def get_by_upload_id(self, upload_id: UUID) -> list[Transaction]:
        stmt = select(TransactionModel).where(
            TransactionModel.upload_id == str(upload_id),
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_shared_by_period(self, year: int, month: int) -> list[Transaction]:
        prefix = date_month_prefix(year, month)
        stmt = select(TransactionModel).where(
            TransactionModel.date.startswith(prefix),
            TransactionModel.is_shared.is_(True),
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_shared_by_year(self, year: int) -> list[Transaction]:
        prefix = f"{year:04d}-"
        stmt = select(TransactionModel).where(
            TransactionModel.date.startswith(prefix),
            TransactionModel.is_shared.is_(True),
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_by_person_and_date_range(
        self, person_id: UUID, start_date: date, end_date: date
    ) -> list[Transaction]:
        stmt = select(TransactionModel).where(
            TransactionModel.payer_person_id == str(person_id),
            TransactionModel.date >= start_date.isoformat(),
            TransactionModel.date <= end_date.isoformat(),
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def update_mutable_fields(self, entity: Transaction) -> Transaction:
        stmt = (
            update(TransactionModel)
            .where(TransactionModel.id == str(entity.id))
            .values(
                merchant=entity.merchant,
                category=entity.category,
                notes=entity.notes,
                tags_json=json.dumps(list(entity.tags)),
                is_shared=entity.is_shared,
                payer_person_id=str(entity.payer_person_id),
                payer_percentage=entity.payer_percentage,
                upload_id=str(entity.upload_id),
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return entity

    async def delete_by_upload_id(self, upload_id: UUID) -> int:
        stmt = delete(TransactionModel).where(
            TransactionModel.upload_id == str(upload_id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        if isinstance(result, CursorResult):
            return result.rowcount
        return 0

    async def get_distinct_categories(self) -> list[str]:
        stmt = select(TransactionModel.category).distinct()
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]
