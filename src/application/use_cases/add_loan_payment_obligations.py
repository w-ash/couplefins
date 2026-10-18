from datetime import UTC, date, datetime
from typing import Final
from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import bounded_int
from src.application.use_cases._shared.entity_lookup import require_by_id
from src.domain.entities.obligation import Obligation
from src.domain.exceptions import ValidationError
from src.domain.obligations import generate_loan_payment_obligations
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

MAX_PAYMENT_MONTHS: Final = 24


@define(frozen=True, slots=True)
class AddLoanPaymentObligationsCommand:
    """Payments fall from the first day of ``today``'s month: today (UTC)
    when None."""

    loan_id: UUID
    months: int = field(validator=bounded_int(1, MAX_PAYMENT_MONTHS))
    today: date | None = None


@define(frozen=True, slots=True)
class AddLoanPaymentObligationsResult:
    obligations: list[Obligation]  # the ones added, in due order


@define(slots=True)
class AddLoanPaymentObligationsUseCase:
    async def execute(
        self, command: AddLoanPaymentObligationsCommand, uow: UnitOfWorkProtocol
    ) -> AddLoanPaymentObligationsResult:
        """Add the loan's next monthly payments as obligations, from its
        schedule: from the first day of this month, only after its latest
        payment obligation, and in months that have none. Fewer are added
        when its term runs out.

        Raise NotFoundError when the loan does not exist, and
        ValidationError when it is closed.
        """
        async with uow:
            loan = await require_by_id(uow.loans.get_by_id, command.loan_id, "Loan")
            if not loan.is_open:
                raise ValidationError(f"Loan {loan.name!r} is closed")
            existing = await uow.obligations.get_by_loan_id(loan.id)
            today = command.today or datetime.now(UTC).date()
            added = generate_loan_payment_obligations(
                loan, existing, command.months, today
            )
            saved = await uow.obligations.save_batch(added)
            await uow.commit()
            return AddLoanPaymentObligationsResult(obligations=saved)
