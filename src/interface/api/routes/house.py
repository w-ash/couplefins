from uuid import UUID

from fastapi import APIRouter, Depends

from src.application.runner import execute_use_case
from src.application.use_cases.add_loan_payment_obligations import (
    AddLoanPaymentObligationsUseCase,
)
from src.application.use_cases.close_loan import CloseLoanUseCase
from src.application.use_cases.create_loan import CreateLoanUseCase
from src.application.use_cases.create_obligation import CreateObligationUseCase
from src.application.use_cases.delete_loan import DeleteLoanCommand, DeleteLoanUseCase
from src.application.use_cases.delete_manual_transaction import (
    DeleteManualTransactionCommand,
    DeleteManualTransactionUseCase,
)
from src.application.use_cases.delete_obligation import (
    DeleteObligationCommand,
    DeleteObligationUseCase,
)
from src.application.use_cases.find_obligation_payment_candidates import (
    FindObligationPaymentCandidatesCommand,
    FindObligationPaymentCandidatesUseCase,
)
from src.application.use_cases.get_co_owned_asset import (
    GetCoOwnedAssetCommand,
    GetCoOwnedAssetUseCase,
)
from src.application.use_cases.get_house import GetHouseCommand, GetHouseUseCase
from src.application.use_cases.list_loans import ListLoansCommand, ListLoansUseCase
from src.application.use_cases.list_manual_transactions import (
    ListManualTransactionsCommand,
    ListManualTransactionsUseCase,
)
from src.application.use_cases.list_obligations import (
    ListObligationsCommand,
    ListObligationsUseCase,
)
from src.application.use_cases.mark_obligation_paid import MarkObligationPaidUseCase
from src.application.use_cases.record_manual_transaction import (
    RecordManualTransactionUseCase,
)
from src.application.use_cases.replace_loan import ReplaceLoanUseCase
from src.application.use_cases.save_co_owned_asset import SaveCoOwnedAssetUseCase
from src.application.use_cases.update_loan_statement import UpdateLoanStatementUseCase
from src.application.use_cases.update_obligation import UpdateObligationUseCase
from src.domain.entities.person import Person
from src.infrastructure.events.event_bus import event_bus
from src.interface.api.dependencies import get_current_user
from src.interface.api.schemas.house import (
    CloseLoanRequest,
    CoOwnedAssetResponse,
    CreateLoanRequest,
    CreateObligationRequest,
    HouseResponse,
    LoanPaymentObligationsRequest,
    LoanRecordResponse,
    LoanStatementRequest,
    ManualEntryResponse,
    ObligationCandidateResponse,
    ObligationPaymentRequest,
    ObligationRecordResponse,
    RecordManualTransactionRequest,
    ReplaceLoanRequest,
    ReplaceLoanResponse,
    SaveCoOwnedAssetRequest,
    UpdateObligationRequest,
)

router = APIRouter(tags=["house"], dependencies=[Depends(get_current_user)])


@router.get("/house")
async def get_house() -> HouseResponse:
    command = GetHouseCommand()
    result = await execute_use_case(lambda uow: GetHouseUseCase().execute(command, uow))
    return HouseResponse.from_result(result)


@router.get("/house/asset")
async def get_co_owned_asset() -> CoOwnedAssetResponse | None:
    command = GetCoOwnedAssetCommand()
    result = await execute_use_case(
        lambda uow: GetCoOwnedAssetUseCase().execute(command, uow)
    )
    return CoOwnedAssetResponse.from_domain(result.asset) if result.asset else None


@router.put("/house/asset")
async def save_co_owned_asset(body: SaveCoOwnedAssetRequest) -> CoOwnedAssetResponse:
    command = body.to_command()
    result = await execute_use_case(
        lambda uow: SaveCoOwnedAssetUseCase().execute(command, uow)
    )
    event_bus.broadcast("house")
    return CoOwnedAssetResponse.from_domain(result.asset)


@router.get("/house/manual-entries")
async def list_manual_entries() -> list[ManualEntryResponse]:
    command = ListManualTransactionsCommand()
    result = await execute_use_case(
        lambda uow: ListManualTransactionsUseCase().execute(command, uow)
    )
    return [ManualEntryResponse.from_domain(tx) for tx in result.transactions]


@router.post("/house/manual-entries", status_code=201)
async def record_manual_entry(
    body: RecordManualTransactionRequest,
    current_user: Person = Depends(get_current_user),
) -> ManualEntryResponse:
    command = body.to_command(entered_by=current_user.id)
    result = await execute_use_case(
        lambda uow: RecordManualTransactionUseCase().execute(command, uow)
    )
    event_bus.broadcast("house", "transactions", "accounts")  # first adds the account
    return ManualEntryResponse.from_domain(result.transaction)


@router.delete("/house/manual-entries/{transaction_id}")
async def delete_manual_entry(transaction_id: UUID) -> dict[str, bool]:
    command = DeleteManualTransactionCommand(transaction_id=transaction_id)
    result = await execute_use_case(
        lambda uow: DeleteManualTransactionUseCase().execute(command, uow)
    )
    event_bus.broadcast("house", "transactions")
    return {"deleted": result.deleted}


@router.get("/house/loans")
async def list_loans() -> list[LoanRecordResponse]:
    command = ListLoansCommand()
    result = await execute_use_case(
        lambda uow: ListLoansUseCase().execute(command, uow)
    )
    return [LoanRecordResponse.model_validate(loan) for loan in result.loans]


@router.post("/house/loans", status_code=201)
async def create_loan(body: CreateLoanRequest) -> LoanRecordResponse:
    command = body.to_command()
    result = await execute_use_case(
        lambda uow: CreateLoanUseCase().execute(command, uow)
    )
    event_bus.broadcast("house")
    return LoanRecordResponse.model_validate(result.loan)


@router.post("/house/loans/{loan_id}/replace", status_code=201)
async def replace_loan(loan_id: UUID, body: ReplaceLoanRequest) -> ReplaceLoanResponse:
    command = body.to_command(loan_id)
    result = await execute_use_case(
        lambda uow: ReplaceLoanUseCase().execute(command, uow)
    )
    event_bus.broadcast("house")
    return ReplaceLoanResponse.model_validate(result)


@router.post("/house/loans/{loan_id}/close")
async def close_loan(loan_id: UUID, body: CloseLoanRequest) -> LoanRecordResponse:
    command = body.to_command(loan_id)
    result = await execute_use_case(
        lambda uow: CloseLoanUseCase().execute(command, uow)
    )
    event_bus.broadcast("house")
    return LoanRecordResponse.model_validate(result.loan)


@router.put("/house/loans/{loan_id}/statement")
async def update_loan_statement(
    loan_id: UUID, body: LoanStatementRequest
) -> LoanRecordResponse:
    command = body.to_command(loan_id)
    result = await execute_use_case(
        lambda uow: UpdateLoanStatementUseCase().execute(command, uow)
    )
    event_bus.broadcast("house")
    return LoanRecordResponse.model_validate(result.loan)


@router.delete("/house/loans/{loan_id}")
async def delete_loan(loan_id: UUID) -> dict[str, bool]:
    command = DeleteLoanCommand(loan_id=loan_id)
    result = await execute_use_case(
        lambda uow: DeleteLoanUseCase().execute(command, uow)
    )
    event_bus.broadcast("house")
    return {"deleted": result.deleted}


@router.post("/house/loans/{loan_id}/payment-obligations", status_code=201)
async def add_loan_payment_obligations(
    loan_id: UUID, body: LoanPaymentObligationsRequest
) -> list[ObligationRecordResponse]:
    command = body.to_command(loan_id)
    result = await execute_use_case(
        lambda uow: AddLoanPaymentObligationsUseCase().execute(command, uow)
    )
    event_bus.broadcast("house")
    return [ObligationRecordResponse.model_validate(o) for o in result.obligations]


@router.get("/house/obligations")
async def list_obligations() -> list[ObligationRecordResponse]:
    command = ListObligationsCommand()
    result = await execute_use_case(
        lambda uow: ListObligationsUseCase().execute(command, uow)
    )
    return [ObligationRecordResponse.model_validate(o) for o in result.obligations]


@router.post("/house/obligations", status_code=201)
async def create_obligation(body: CreateObligationRequest) -> ObligationRecordResponse:
    command = body.to_command()
    result = await execute_use_case(
        lambda uow: CreateObligationUseCase().execute(command, uow)
    )
    event_bus.broadcast("house")
    return ObligationRecordResponse.model_validate(result.obligation)


@router.put("/house/obligations/{obligation_id}")
async def update_obligation(
    obligation_id: UUID, body: UpdateObligationRequest
) -> ObligationRecordResponse:
    command = body.to_command(obligation_id)
    result = await execute_use_case(
        lambda uow: UpdateObligationUseCase().execute(command, uow)
    )
    event_bus.broadcast("house")
    return ObligationRecordResponse.model_validate(result.obligation)


@router.delete("/house/obligations/{obligation_id}")
async def delete_obligation(obligation_id: UUID) -> dict[str, bool]:
    command = DeleteObligationCommand(obligation_id=obligation_id)
    result = await execute_use_case(
        lambda uow: DeleteObligationUseCase().execute(command, uow)
    )
    event_bus.broadcast("house")
    return {"deleted": result.deleted}


@router.put("/house/obligations/{obligation_id}/payment")
async def mark_obligation_paid(
    obligation_id: UUID, body: ObligationPaymentRequest
) -> ObligationRecordResponse:
    command = body.to_command(obligation_id)
    result = await execute_use_case(
        lambda uow: MarkObligationPaidUseCase().execute(command, uow)
    )
    event_bus.broadcast("house")
    return ObligationRecordResponse.model_validate(result.obligation)


@router.get("/house/obligations/{obligation_id}/candidates")
async def find_obligation_payment_candidates(
    obligation_id: UUID,
) -> list[ObligationCandidateResponse]:
    command = FindObligationPaymentCandidatesCommand(obligation_id=obligation_id)
    result = await execute_use_case(
        lambda uow: FindObligationPaymentCandidatesUseCase().execute(command, uow)
    )
    return [ObligationCandidateResponse.from_domain(c) for c in result.candidates]
