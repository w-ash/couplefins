from datetime import date
from decimal import Decimal
from uuid import UUID

import attrs
from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    as_validation_error,
    quantize_cents,
)
from src.application.use_cases._shared.entity_lookup import require_by_id
from src.domain.entities.loan import Loan
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UpdateLoanStatementCommand:
    """The balance on the servicer's statement of ``as_of``."""

    loan_id: UUID
    balance: Decimal = field(converter=quantize_cents)
    as_of: date


@define(frozen=True, slots=True)
class UpdateLoanStatementResult:
    loan: Loan


@define(slots=True)
class UpdateLoanStatementUseCase:
    async def execute(
        self, command: UpdateLoanStatementCommand, uow: UnitOfWorkProtocol
    ) -> UpdateLoanStatementResult:
        """Re-anchor a loan's balance on a new statement: payments on or
        before its date no longer count. The one edit a loan takes in place.
        Raise NotFoundError when the loan does not exist, and
        ValidationError when the balance is negative."""
        async with uow:
            loan = await require_by_id(uow.loans.get_by_id, command.loan_id, "Loan")
            anchored = as_validation_error(
                attrs.evolve,
                loan,
                statement_balance=command.balance,
                statement_balance_as_of=command.as_of,
            )
            saved = await uow.loans.save(anchored)
            await uow.commit()
            return UpdateLoanStatementResult(loan=saved)
