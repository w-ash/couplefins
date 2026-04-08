from datetime import datetime
from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class ImportEvent:
    person_id: UUID
    imported_at: datetime
