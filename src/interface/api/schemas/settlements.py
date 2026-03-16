import datetime
from uuid import UUID

from pydantic import BaseModel

from src.application.use_cases._shared.settlement_records import SettlementRecord
from src.application.use_cases.get_settle_up_data import GetSettleUpDataResult
from src.domain.entities.settlement import Settlement, SettlementMethod
from src.interface.api.schemas.dashboard import PersonResponse
from src.interface.api.schemas.reconciliation import (
    SettlementResponse as OwedResponse,
    UploadStatusResponse,
)


class RecordSettlementRequest(BaseModel):
    year: int
    month: int
    amount: float
    from_person_id: UUID
    to_person_id: UUID
    method: SettlementMethod
    notes: str = ""
    settled_at: datetime.datetime | None = None
    linked_transaction_ids: list[UUID] = []


class RecordWaivedSettlementRequest(BaseModel):
    year: int
    month: int
    from_person_id: UUID
    to_person_id: UUID
    notes: str = ""


class MarkTransactionRequest(BaseModel):
    transaction_id: UUID
    settlement_id: UUID | None = None
    is_settlement: bool = True


class SettlementResponse(BaseModel):
    id: UUID
    year: int
    month: int
    amount: float
    from_person_id: UUID
    to_person_id: UUID
    method: str | None
    is_waived: bool
    notes: str
    settled_at: datetime.datetime
    created_at: datetime.datetime
    linked_transaction_ids: list[UUID]

    @classmethod
    def from_domain(
        cls, settlement: Settlement, linked_tx_ids: list[UUID] | None = None
    ) -> SettlementResponse:
        return cls(
            id=settlement.id,
            year=settlement.year,
            month=settlement.month,
            amount=float(settlement.amount),
            from_person_id=settlement.from_person_id,
            to_person_id=settlement.to_person_id,
            method=settlement.method.value if settlement.method else None,
            is_waived=settlement.is_waived,
            notes=settlement.notes,
            settled_at=settlement.settled_at,
            created_at=settlement.created_at,
            linked_transaction_ids=linked_tx_ids or [],
        )

    @classmethod
    def from_record(cls, record: SettlementRecord) -> SettlementResponse:
        return cls.from_domain(record.settlement, record.linked_transaction_ids)


class SettleUpDataResponse(BaseModel):
    year: int
    month: int
    owed: OwedResponse | None
    recorded_settlements: list[SettlementResponse]
    remaining_balance: float
    upload_statuses: list[UploadStatusResponse]
    persons: list[PersonResponse]
    is_finalized: bool
    finalized_at: datetime.datetime | None

    @classmethod
    def from_result(cls, result: GetSettleUpDataResult) -> SettleUpDataResponse:
        return cls(
            year=result.year,
            month=result.month,
            owed=OwedResponse.from_domain(result.owed) if result.owed else None,
            recorded_settlements=[
                SettlementResponse.from_record(r) for r in result.recorded_settlements
            ],
            remaining_balance=float(result.remaining_balance),
            upload_statuses=[
                UploadStatusResponse.from_domain(us) for us in result.upload_statuses
            ],
            persons=[PersonResponse(id=p.id, name=p.name) for p in result.persons],
            is_finalized=result.is_finalized,
            finalized_at=result.finalized_at,
        )


class DeleteSettlementResponse(BaseModel):
    deleted: bool


class MarkTransactionResponse(BaseModel):
    transaction_id: UUID
    is_settlement: bool
