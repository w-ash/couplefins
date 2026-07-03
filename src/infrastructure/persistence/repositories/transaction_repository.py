from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    cast,
    func,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.domain.constants import SplitDefaults
from src.domain.entities.transaction import Transaction
from src.infrastructure.persistence.models.transaction_model import TransactionModel
from src.infrastructure.persistence.repositories.base import (
    BaseRepository,
    date_year_prefix,
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
            tags=tuple(model.tags),
            payer_person_id=UUID(model.payer_person_id),
            payer_percentage=model.payer_percentage,
            household=model.household,
            is_settlement=model.is_settlement,
            is_excluded=model.is_excluded,
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
            "tags": list(entity.tags),
            "household": entity.household,
            "payer_person_id": str(entity.payer_person_id),
            "payer_percentage": entity.payer_percentage,
            "is_settlement": entity.is_settlement,
            "is_excluded": entity.is_excluded,
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

    async def save_batch(self, entities: list[Transaction]) -> list[Transaction]:
        if not entities:
            return []
        values = [self._to_column_values(e) for e in entities]
        await self._session.execute(insert(TransactionModel), values)
        await self._session.flush()
        return entities

    async def update_mutable_fields_batch(
        self, entities: list[Transaction]
    ) -> list[Transaction]:
        """Batch update for CSV re-upload — accepted "changed" rows only.

        Excludes _IN_APP_KEYS on top of the usual write set: freshly parsed
        rows always carry is_settlement/is_excluded defaults, and writing
        them would silently revert flags set in-app (settlement linking,
        exclusion toggle). The singular update_mutable_fields keeps writing
        those flags — it serves the mark/unlink flows that flip them.
        """
        if not entities:
            return []
        exclude = self._IMMUTABLE_KEYS | self._UPLOAD_ONLY_KEYS | self._IN_APP_KEYS
        params: list[dict[str, object]] = []
        for entity in entities:
            vals = self._to_column_values(entity)
            for k in exclude:
                del vals[k]
            params.append(vals)
        # ORM "bulk UPDATE by primary key": no WHERE/VALUES — each param dict
        # carries the pk plus the columns to write. A hand-rolled WHERE with
        # bindparams trips ORM session synchronization instead.
        await self._session.execute(update(TransactionModel), params)
        await self._session.flush()
        return entities

    async def _query(self, *filters: ColumnElement[bool]) -> list[Transaction]:
        stmt = select(TransactionModel).where(*filters)
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    @staticmethod
    def _tag_filter(tags: tuple[str, ...] | None) -> list[ColumnElement[bool]]:
        if not tags:
            return []
        return [TransactionModel.tags.op("@>")(cast([t.lower() for t in tags], JSONB))]

    async def get_by_date_range(
        self, start_date: date, end_date: date
    ) -> list[Transaction]:
        return await self._query(
            TransactionModel.date >= start_date.isoformat(),
            TransactionModel.date <= end_date.isoformat(),
        )

    async def get_household_by_year(self, year: int) -> list[Transaction]:
        return await self._query(
            TransactionModel.date.startswith(date_year_prefix(year)),
            TransactionModel.household.is_(True),
            TransactionModel.is_settlement.is_(False),
        )

    async def get_by_year(self, year: int) -> list[Transaction]:
        return await self._query(
            TransactionModel.date.startswith(date_year_prefix(year)),
            TransactionModel.is_settlement.is_(False),
        )

    async def get_household_by_date_range(
        self,
        start_date: date,
        end_date: date,
        *,
        tags: tuple[str, ...] | None = None,
    ) -> list[Transaction]:
        return await self._query(
            TransactionModel.date >= start_date.isoformat(),
            TransactionModel.date <= end_date.isoformat(),
            TransactionModel.household.is_(True),
            TransactionModel.is_settlement.is_(False),
            *self._tag_filter(tags),
        )

    async def get_settlement_relevant_by_date_range(
        self,
        start_date: date,
        end_date: date,
        *,
        tags: tuple[str, ...] | None = None,
    ) -> list[Transaction]:
        return await self._query(
            TransactionModel.date >= start_date.isoformat(),
            TransactionModel.date <= end_date.isoformat(),
            TransactionModel.payer_percentage < SplitDefaults.MAX_PAYER_PERCENTAGE,
            TransactionModel.is_settlement.is_(False),
            TransactionModel.is_excluded.is_(False),
            *self._tag_filter(tags),
        )

    async def get_by_person_and_date_range(
        self,
        person_id: UUID,
        start_date: date,
        end_date: date,
        *,
        tags: tuple[str, ...] | None = None,
    ) -> list[Transaction]:
        return await self._query(
            TransactionModel.payer_person_id == str(person_id),
            TransactionModel.date >= start_date.isoformat(),
            TransactionModel.date <= end_date.isoformat(),
            *self._tag_filter(tags),
        )

    async def get_by_person_and_original_date_range(
        self,
        person_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[Transaction]:
        """Dedup fetch for CSV re-upload: match rows by the date the CSV knows
        (original_date when the current date was edited in-app), so edited
        rows still pair with their CSV twins instead of duplicating.
        ISO-string comparison is chronological.
        """
        effective_date = func.coalesce(
            TransactionModel.original_date, TransactionModel.date
        )
        return await self._query(
            TransactionModel.payer_person_id == str(person_id),
            effective_date >= start_date.isoformat(),
            effective_date <= end_date.isoformat(),
        )

    _IMMUTABLE_KEYS = frozenset({"account", "original_statement", "occurrence"})
    _UPLOAD_ONLY_KEYS = frozenset({
        "date",
        "amount",
        "original_date",
        "original_amount",
    })
    # Flags owned by in-app actions (settlement linking, exclusion toggle) —
    # never overwritten by the re-upload batch path.
    _IN_APP_KEYS = frozenset({"is_settlement", "is_excluded"})

    async def _update(
        self, entity: Transaction, exclude: frozenset[str]
    ) -> Transaction:
        values = self._to_column_values(entity)
        entity_id = values.pop("id")
        for k in exclude:
            del values[k]
        stmt = (
            update(TransactionModel)
            .where(TransactionModel.id == entity_id)
            .values(**values)
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return entity

    async def update_mutable_fields(self, entity: Transaction) -> Transaction:
        return await self._update(entity, self._IMMUTABLE_KEYS | self._UPLOAD_ONLY_KEYS)

    async def update_all_fields(self, entity: Transaction) -> Transaction:
        return await self._update(entity, self._IMMUTABLE_KEYS)

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

    async def get_distinct_tags(self) -> list[str]:
        stmt = (
            select(func.jsonb_array_elements_text(TransactionModel.tags).label("tag"))
            .distinct()
            .order_by(text("tag"))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars())
