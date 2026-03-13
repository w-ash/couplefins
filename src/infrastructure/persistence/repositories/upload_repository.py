from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select

from src.domain.entities.upload import Upload
from src.infrastructure.persistence.models.transaction_model import TransactionModel
from src.infrastructure.persistence.models.upload_model import UploadModel
from src.infrastructure.persistence.repositories.base import (
    BaseRepository,
    date_month_prefix,
)


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

    async def get_by_person_ids_with_transactions_in_period(
        self, person_ids: list[UUID], year: int, month: int
    ) -> list[Upload]:
        if not person_ids:
            return []
        prefix = date_month_prefix(year, month)
        person_id_strs = [str(pid) for pid in person_ids]
        subq = (
            select(TransactionModel.upload_id)
            .where(TransactionModel.date.startswith(prefix))
            .where(TransactionModel.payer_person_id.in_(person_id_strs))
            .distinct()
            .subquery()
        )
        stmt = select(UploadModel).where(UploadModel.id.in_(select(subq)))
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_by_person_ids_with_transactions_in_date_range(
        self, person_ids: list[UUID], start_date: date, end_date: date
    ) -> list[Upload]:
        if not person_ids:
            return []
        person_id_strs = [str(pid) for pid in person_ids]
        subq = (
            select(TransactionModel.upload_id)
            .where(TransactionModel.date >= start_date.isoformat())
            .where(TransactionModel.date <= end_date.isoformat())
            .where(TransactionModel.payer_person_id.in_(person_id_strs))
            .distinct()
            .subquery()
        )
        stmt = select(UploadModel).where(UploadModel.id.in_(select(subq)))
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]
