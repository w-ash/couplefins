from datetime import date
from decimal import Decimal
import json
from typing import cast
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
            tags=tuple(cast(list[str], json.loads(model.tags_json))),
            payer_person_id=UUID(model.payer_person_id),
            payer_percentage=model.payer_percentage,
            household=model.household,
            is_settlement=model.is_settlement,
            original_date=(
                date.fromisoformat(model.original_date) if model.original_date else None
            ),
            original_amount=(
                Decimal(model.original_amount) if model.original_amount else None
            ),
        )

    @staticmethod
    def _to_column_values(entity: Transaction) -> dict[str, object]:
        return {
            "id": str(entity.id),
            "upload_id": str(entity.upload_id),
            "date": entity.date.isoformat(),
            "merchant": entity.merchant,
            "category": entity.category,
            "account": entity.account,
            "original_statement": entity.original_statement,
            "occurrence": entity.occurrence,
            "notes": entity.notes,
            "amount": str(entity.amount),
            "tags_json": json.dumps(list(entity.tags)),
            "household": entity.household,
            "payer_person_id": str(entity.payer_person_id),
            "payer_percentage": entity.payer_percentage,
            "is_settlement": entity.is_settlement,
            "original_date": (
                entity.original_date.isoformat() if entity.original_date else None
            ),
            "original_amount": (
                str(entity.original_amount)
                if entity.original_amount is not None
                else None
            ),
        }

    @staticmethod
    def _to_model(entity: Transaction) -> TransactionModel:
        return TransactionModel(**TransactionRepository._to_column_values(entity))

    async def get_by_upload_id(self, upload_id: UUID) -> list[Transaction]:
        stmt = select(TransactionModel).where(
            TransactionModel.upload_id == str(upload_id),
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_household_by_period(self, year: int, month: int) -> list[Transaction]:
        prefix = date_month_prefix(year, month)
        stmt = select(TransactionModel).where(
            TransactionModel.date.startswith(prefix),
            TransactionModel.household.is_(True),
            TransactionModel.is_settlement.is_(False),
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_household_by_year(self, year: int) -> list[Transaction]:
        prefix = f"{year:04d}-"
        stmt = select(TransactionModel).where(
            TransactionModel.date.startswith(prefix),
            TransactionModel.household.is_(True),
            TransactionModel.is_settlement.is_(False),
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_by_year(self, year: int) -> list[Transaction]:
        prefix = f"{year:04d}-"
        stmt = select(TransactionModel).where(
            TransactionModel.date.startswith(prefix),
            TransactionModel.is_settlement.is_(False),
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_household_by_date_range(
        self, start_date: date, end_date: date
    ) -> list[Transaction]:
        stmt = select(TransactionModel).where(
            TransactionModel.date >= start_date.isoformat(),
            TransactionModel.date <= end_date.isoformat(),
            TransactionModel.household.is_(True),
            TransactionModel.is_settlement.is_(False),
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
        values = self._to_column_values(entity)
        entity_id = values.pop("id")
        for k in (
            "account",
            "original_statement",
            "occurrence",
            "date",
            "amount",
            "original_date",
            "original_amount",
        ):
            del values[k]
        stmt = (
            update(TransactionModel)
            .where(TransactionModel.id == entity_id)
            .values(**values)
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return entity

    async def update_all_fields(self, entity: Transaction) -> Transaction:
        values = self._to_column_values(entity)
        entity_id = values.pop("id")
        for k in ("account", "original_statement", "occurrence"):
            del values[k]
        stmt = (
            update(TransactionModel)
            .where(TransactionModel.id == entity_id)
            .values(**values)
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

    async def get_latest_household_transaction_date(self) -> date | None:
        stmt = (
            select(TransactionModel.date)
            .where(
                TransactionModel.household.is_(True),
                TransactionModel.is_settlement.is_(False),
            )
            .order_by(TransactionModel.date.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        value = result.scalar_one_or_none()
        return date.fromisoformat(value) if value else None

    async def get_distinct_categories(self) -> list[str]:
        stmt = select(TransactionModel.category).distinct()
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_distinct_tags(self) -> list[str]:
        stmt = select(TransactionModel.tags_json).distinct()
        result = await self._session.execute(stmt)
        tags: set[str] = set()
        for tags_json in result.scalars():
            tags.update(cast(list[str], json.loads(tags_json)))
        return sorted(tags)
