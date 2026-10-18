from uuid import UUID

from attrs import define

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.transaction_reads import fetch_labelled_rows
from src.domain.exceptions import ValidationError
from src.domain.loans import linked_rows, loan_tag
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class DeleteLoanCommand:
    loan_id: UUID


@define(frozen=True, slots=True)
class DeleteLoanResult:
    deleted: bool


@define(slots=True)
class DeleteLoanUseCase:
    async def execute(
        self, command: DeleteLoanCommand, uow: UnitOfWorkProtocol
    ) -> DeleteLoanResult:
        """Delete a loan entered by mistake: a loan's terms cannot be edited,
        so a typo is fixed by deleting and entering it again.

        Raise NotFoundError when the loan does not exist, and ValidationError
        once it has history: a row tagged with it, an obligation, or a loan
        it replaced.
        """
        async with uow:
            loan = await require_by_id(uow.loans.get_by_id, command.loan_id, "Loan")
            tag = loan_tag(loan)
            if linked_rows(loan, await fetch_labelled_rows(uow, tag)):
                raise ValidationError(
                    f"Rows are tagged {tag}; remove the tag from them first"
                )
            if await uow.obligations.get_by_loan_id(loan.id):
                raise ValidationError(
                    f"Loan {loan.name!r} has obligations; delete them first"
                )
            if await uow.loans.exists_replaced_by(loan.id):
                raise ValidationError(
                    f"Loan {loan.name!r} replaced another loan and keeps its history"
                )
            await uow.loans.delete(loan.id)
            await uow.commit()
            return DeleteLoanResult(deleted=True)
