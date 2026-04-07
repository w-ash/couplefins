from datetime import date, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import ColumnElement, case, func, select

from src.domain.entities.upload import Upload, UploadWithCounts
from src.infrastructure.persistence.models.transaction_model import TransactionModel
from src.infrastructure.persistence.models.upload_model import UploadModel
from src.infrastructure.persistence.repositories.base import (
    BaseRepository,
    date_month_prefix,
)

type _UploadCountsRow = tuple[
    str, str, str, str, int, int | None, str | None, str | None
]


class UploadRepository(BaseRepository[Upload, UploadModel]):
    _model_class = UploadModel

    @staticmethod
    def _to_domain(model: UploadModel) -> Upload:
        return Upload(
            id=UUID(model.id),
            person_id=UUID(model.person_id),
            filename=model.filename,
            uploaded_at=datetime.fromisoformat(model.uploaded_at),
        )

    @staticmethod
    def _to_model(entity: Upload) -> UploadModel:
        return UploadModel(
            id=str(entity.id),
            person_id=str(entity.person_id),
            filename=entity.filename,
            uploaded_at=entity.uploaded_at.isoformat(),
        )

    async def _uploads_with_transactions(
        self, person_ids: list[UUID], *date_filters: ColumnElement[bool]
    ) -> list[Upload]:
        if not person_ids:
            return []
        person_id_strs = [str(pid) for pid in person_ids]
        subq = (
            select(TransactionModel.upload_id)
            .where(*date_filters)
            .where(TransactionModel.payer_person_id.in_(person_id_strs))
            .distinct()
            .subquery()
        )
        stmt = select(UploadModel).where(UploadModel.id.in_(select(subq)))
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_by_person_ids_with_transactions_in_period(
        self, person_ids: list[UUID], year: int, month: int
    ) -> list[Upload]:
        prefix = date_month_prefix(year, month)
        return await self._uploads_with_transactions(
            person_ids,
            TransactionModel.date.startswith(prefix),
        )

    async def get_by_person_ids_with_transactions_in_date_range(
        self, person_ids: list[UUID], start_date: date, end_date: date
    ) -> list[Upload]:
        return await self._uploads_with_transactions(
            person_ids,
            TransactionModel.date >= start_date.isoformat(),
            TransactionModel.date <= end_date.isoformat(),
        )

    async def get_all_with_transaction_counts(self) -> list[UploadWithCounts]:

        tx = TransactionModel
        stmt = (
            select(
                UploadModel.id,
                UploadModel.person_id,
                UploadModel.filename,
                UploadModel.uploaded_at,
                func.count(tx.id).label("transaction_count"),
                func.sum(case((tx.household.is_(True), 1), else_=0)).label(
                    "household_count"
                ),
                func.min(tx.date).label("date_range_start"),
                func.max(tx.date).label("date_range_end"),
            )
            .outerjoin(tx, UploadModel.id == tx.upload_id)
            .group_by(UploadModel.id)
            .order_by(UploadModel.uploaded_at.desc())
        )
        result = await self._session.execute(stmt)
        rows = cast(list[_UploadCountsRow], result.tuples().all())
        return [
            UploadWithCounts(
                id=UUID(id_),
                person_id=UUID(person_id),
                filename=filename,
                uploaded_at=datetime.fromisoformat(uploaded_at),
                transaction_count=tx_count,
                household_count=hh_count or 0,
                date_range_start=date.fromisoformat(dr_start) if dr_start else None,
                date_range_end=date.fromisoformat(dr_end) if dr_end else None,
            )
            for id_, person_id, filename, uploaded_at, tx_count, hh_count, dr_start, dr_end in rows
        ]
