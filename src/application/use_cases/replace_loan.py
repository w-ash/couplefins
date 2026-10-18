from datetime import date
from uuid import UUID

from attrs import define

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.house_records import (
    LoanTerms,
    add_loan,
    close_loan,
)
from src.domain.entities.loan import Loan
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ReplaceLoanCommand:
    """A refinance: ``replacement`` takes over the loan on ``closed_on``."""

    loan_id: UUID
    closed_on: date
    replacement: LoanTerms


@define(frozen=True, slots=True)
class ReplaceLoanResult:
    replaced: Loan  # closed, naming its replacement
    replacement: Loan


@define(slots=True)
class ReplaceLoanUseCase:
    async def execute(
        self, command: ReplaceLoanCommand, uow: UnitOfWorkProtocol
    ) -> ReplaceLoanResult:
        """Replace an open loan with a new one, as at a refinance.

        The old loan closes on `closed_on` and names its replacement; it
        keeps its terms, payments, and paid obligations. Raise NotFoundError
        when the loan does not exist, and ValidationError when it is closed
        already or a value of either loan is rejected.
        """
        async with uow:
            loan = await require_by_id(uow.loans.get_by_id, command.loan_id, "Loan")
            replacement = await add_loan(uow, command.replacement, loan.asset_id)
            replaced = await close_loan(
                uow, loan, command.closed_on, replaced_by=replacement.id
            )
            await uow.commit()
            return ReplaceLoanResult(replaced=replaced, replacement=replacement)
