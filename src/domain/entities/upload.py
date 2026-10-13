from datetime import date, datetime
from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class Upload:
    id: UUID
    person_id: UUID
    filename: str
    uploaded_at: datetime
    importer: str
    # Hex SHA-256 of the imported file, for provenance. None on uploads made before
    # files were hashed.
    content_sha256: str | None


@define(frozen=True, slots=True)
class UploadWithCounts:
    id: UUID
    person_id: UUID
    filename: str
    uploaded_at: datetime
    transaction_count: int
    household_count: int
    date_range_start: date | None
    date_range_end: date | None
