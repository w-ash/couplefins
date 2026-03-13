from datetime import datetime
from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class TransactionEdit:
    id: UUID
    transaction_id: UUID
    field_name: str
    old_value: str
    new_value: str
    edited_at: datetime
