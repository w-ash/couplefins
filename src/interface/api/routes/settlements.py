from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends

from src.application.runner import execute_use_case
from src.application.use_cases.delete_settlement import (
    DeleteSettlementCommand,
    DeleteSettlementUseCase,
)
from src.application.use_cases.find_settlement_candidates import (
    FindSettlementCandidatesCommand,
    FindSettlementCandidatesUseCase,
)
from src.application.use_cases.get_settle_up_data import (
    GetSettleUpDataCommand,
    GetSettleUpDataUseCase,
)
from src.application.use_cases.mark_transaction_as_settlement import (
    MarkTransactionAsSettlementCommand,
    MarkTransactionAsSettlementUseCase,
)
from src.application.use_cases.record_settlement import (
    RecordSettlementCommand,
    RecordSettlementUseCase,
)
from src.application.use_cases.record_waived_settlement import (
    RecordWaivedSettlementCommand,
    RecordWaivedSettlementUseCase,
)
from src.application.use_cases.unlink_settlement_transaction import (
    UnlinkSettlementTransactionCommand,
    UnlinkSettlementTransactionUseCase,
)
from src.domain.entities.person import Person
from src.domain.exceptions import ValidationError
from src.infrastructure.events.event_bus import event_bus
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.settlements import (
    DeleteSettlementResponse,
    MarkTransactionRequest,
    MarkTransactionResponse,
    RecordSettlementRequest,
    RecordWaivedSettlementRequest,
    SettlementCandidateResponse,
    SettlementResponse,
    SettleUpDataResponse,
)

router = APIRouter(tags=["settlements"], dependencies=[Depends(get_current_user)])


def _assert_participant(current_user: Person, from_id: UUID, to_id: UUID) -> None:
    if current_user.id not in {from_id, to_id}:
        raise ValidationError("You must be a participant in the settlement")


@router.post("/settlements", status_code=201)
async def record_settlement(
    body: RecordSettlementRequest,
    current_user: Person = Depends(get_current_user),
) -> SettlementResponse:
    _assert_participant(current_user, body.from_person_id, body.to_person_id)
    command = RecordSettlementCommand(
        year=body.year,
        month=body.month,
        amount=Decimal(str(body.amount)),
        from_person_id=body.from_person_id,
        to_person_id=body.to_person_id,
        method=body.method,
        notes=body.notes,
        settled_at=body.settled_at,
        linked_transaction_ids=body.linked_transaction_ids,
    )
    result = await execute_use_case(
        lambda uow: RecordSettlementUseCase().execute(command, uow)
    )
    event_bus.broadcast("settlements")
    return SettlementResponse.from_domain(result.settlement)


@router.post("/settlements/waive", status_code=201)
async def waive_settlement(
    body: RecordWaivedSettlementRequest,
    current_user: Person = Depends(get_current_user),
) -> SettlementResponse:
    _assert_participant(current_user, body.from_person_id, body.to_person_id)
    command = RecordWaivedSettlementCommand(
        year=body.year,
        month=body.month,
        from_person_id=body.from_person_id,
        to_person_id=body.to_person_id,
        notes=body.notes,
    )
    result = await execute_use_case(
        lambda uow: RecordWaivedSettlementUseCase().execute(command, uow)
    )
    event_bus.broadcast("settlements")
    return SettlementResponse.from_domain(result.settlement)


@router.get("/settle-up")
async def get_settle_up_data(year: int, month: int) -> SettleUpDataResponse:
    command = GetSettleUpDataCommand(year=year, month=month)
    result = await execute_use_case(
        lambda uow: GetSettleUpDataUseCase().execute(command, uow)
    )
    return SettleUpDataResponse.from_result(result)


@router.delete("/settlements/{settlement_id}", status_code=200)
async def delete_settlement(
    settlement_id: UUID,
    _current_user: Person = Depends(get_current_user),
) -> DeleteSettlementResponse:
    command = DeleteSettlementCommand(settlement_id=settlement_id)
    result = await execute_use_case(
        lambda uow: DeleteSettlementUseCase().execute(command, uow)
    )
    event_bus.broadcast("settlements")
    return DeleteSettlementResponse(deleted=result.deleted)


@router.post("/settlements/mark-transaction", status_code=200)
async def mark_transaction_as_settlement(
    body: MarkTransactionRequest,
    _current_user: Person = Depends(get_current_user),
) -> MarkTransactionResponse:
    command = MarkTransactionAsSettlementCommand(
        transaction_id=body.transaction_id,
        settlement_id=body.settlement_id,
        is_settlement=body.is_settlement,
    )
    result = await execute_use_case(
        lambda uow: MarkTransactionAsSettlementUseCase().execute(command, uow)
    )
    event_bus.broadcast("settlements")
    return MarkTransactionResponse(
        transaction_id=result.transaction_id,
        is_settlement=result.is_settlement,
    )


@router.get("/settlements/candidates")
async def get_settlement_candidates(
    year: int,
    month: int,
    amount: float,
    search_year: int | None = None,
    search_month: int | None = None,
) -> list[SettlementCandidateResponse]:
    command = FindSettlementCandidatesCommand(
        year=year,
        month=month,
        amount=Decimal(str(amount)),
        search_year=search_year,
        search_month=search_month,
    )
    result = await execute_use_case(
        lambda uow: FindSettlementCandidatesUseCase().execute(command, uow)
    )
    return [SettlementCandidateResponse.from_domain(c) for c in result.candidates]


@router.delete("/settlements/{settlement_id}/links/{transaction_id}")
async def unlink_settlement_transaction(
    settlement_id: UUID,
    transaction_id: UUID,
    _current_user: Person = Depends(get_current_user),
) -> dict[str, bool]:
    command = UnlinkSettlementTransactionCommand(
        settlement_id=settlement_id, transaction_id=transaction_id
    )
    result = await execute_use_case(
        lambda uow: UnlinkSettlementTransactionUseCase().execute(command, uow)
    )
    event_bus.broadcast("settlements")
    return {"unlinked": result.unlinked}
