from datetime import date
from uuid import UUID

from attrs import define

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.house_records import close_loan
from src.domain.entities.loan import Loan
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class CloseLoanCommand:
    loan_id: UUID
    closed_on: date


@define(frozen=True, slots=True)
class CloseLoanResult:
    loan: Loan


@define(slots=True)
class CloseLoanUseCase:
    async def execute(
        self, command: CloseLoanCommand, uow: UnitOfWorkProtocol
    ) -> CloseLoanResult:
        """Close a loan no longer carried, on any date: a bridge loan is often
        paid off before its first due date. It leaves the open loans and
        keeps its history; its unpaid payment obligations due after
        `closed_on` are deleted. Raise NotFoundError when the loan does not
        exist, and ValidationError when it is closed already."""
        async with uow:
            loan = await require_by_id(uow.loans.get_by_id, command.loan_id, "Loan")
            closed = await close_loan(uow, loan, command.closed_on)
            await uow.commit()
            return CloseLoanResult(loan=closed)
