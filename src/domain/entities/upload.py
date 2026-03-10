from datetime import datetime
from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class Upload:
    id: UUID
    person_id: UUID
    filename: str
    uploaded_at: datetime
    period_year: int
    period_month: int
