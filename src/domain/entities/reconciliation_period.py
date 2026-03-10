from datetime import datetime
from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class ReconciliationPeriod:
    id: UUID
    year: int
    month: int
    is_finalized: bool
    finalized_at: datetime | None
    notes: str
    created_at: datetime
