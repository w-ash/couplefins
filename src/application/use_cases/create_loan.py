from attrs import define

from src.application.use_cases._shared.house_records import (
    LoanTerms,
    add_loan,
    require_asset,
)
from src.domain.entities.loan import Loan
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class CreateLoanCommand:
    terms: LoanTerms


@define(frozen=True, slots=True)
class CreateLoanResult:
    loan: Loan


@define(slots=True)
class CreateLoanUseCase:
    async def execute(
        self, command: CreateLoanCommand, uow: UnitOfWorkProtocol
    ) -> CreateLoanResult:
        """Record a loan on the couple's home. Its payment rows link to it
        by the tag `loan:<slug>`, the slug from its name.

        Raise ValidationError before the home is set up, when the name gives
        no slug or another loan's slug, and when a term is out of range.
        """
        async with uow:
            asset = await require_asset(uow)
            loan = await add_loan(uow, command.terms, asset.id)
            await uow.commit()
            return CreateLoanResult(loan=loan)
