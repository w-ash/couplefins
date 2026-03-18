from datetime import date, datetime
from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class Upload:
    id: UUID
    person_id: UUID
    filename: str
    uploaded_at: datetime


@define(frozen=True, slots=True)
class UploadWithCounts:
    id: UUID
    person_id: UUID
    filename: str
    uploaded_at: datetime
    transaction_count: int
    shared_count: int
    date_range_start: date | None
    date_range_end: date | None
