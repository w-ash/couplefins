from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from src.domain.entities.upload import Upload
from src.infrastructure.persistence.models.upload_model import UploadModel
from src.infrastructure.persistence.repositories.base import BaseRepository


class UploadRepository(BaseRepository[Upload, UploadModel]):
    _model_class = UploadModel

    @staticmethod
    def _to_domain(model: UploadModel) -> Upload:
        return Upload(
            id=UUID(model.id),
            person_id=UUID(model.person_id),
            filename=model.filename,
            uploaded_at=datetime.fromisoformat(model.uploaded_at),
            period_year=model.period_year,
            period_month=model.period_month,
        )

    @staticmethod
    def _to_model(entity: Upload) -> UploadModel:
        return UploadModel(
            id=str(entity.id),
            person_id=str(entity.person_id),
            filename=entity.filename,
            uploaded_at=entity.uploaded_at.isoformat(),
            period_year=entity.period_year,
            period_month=entity.period_month,
        )

    async def get_by_period(self, year: int, month: int) -> list[Upload]:
        stmt = select(UploadModel).where(
            UploadModel.period_year == year,
            UploadModel.period_month == month,
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]
