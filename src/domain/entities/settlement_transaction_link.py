from uuid import UUID

from attrs import define


@define(frozen=True, slots=True)
class SettlementTransactionLink:
    id: UUID
    settlement_id: UUID
    transaction_id: UUID
