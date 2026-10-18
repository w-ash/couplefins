from datetime import date, datetime
from typing import Final
import uuid
from uuid import UUID

from attrs import define

# The importer of the one upload that holds a hand-entered account's rows. It
# reads no file, so Upload history leaves it out.
MANUAL_IMPORTER: Final = "manual"


def manual_upload_id(account_id: UUID) -> UUID:
    """Return the id of the upload that holds the account's hand-entered rows.

    The id derives from the account, so every entry finds the same upload.
    """
    return uuid.uuid5(account_id, MANUAL_IMPORTER)


@define(frozen=True, slots=True)
class Upload:
    id: UUID
    person_id: UUID
    filename: str
    uploaded_at: datetime
    importer: str
    # Hex SHA-256 of the imported file, for provenance. None on uploads made before
    # files were hashed, and on a manual upload.
    content_sha256: str | None

    @property
    def is_manual(self) -> bool:
        """True for the upload of a hand-entered account's rows."""
        return self.importer == MANUAL_IMPORTER


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
