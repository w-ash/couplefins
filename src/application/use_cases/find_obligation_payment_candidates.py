from uuid import UUID

from attrs import define

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.transaction_reads import fetch_listed_rows
from src.domain.obligations import (
    PaymentCandidate,
    candidate_window,
    find_payment_candidates,
)
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class FindObligationPaymentCandidatesCommand:
    obligation_id: UUID


@define(frozen=True, slots=True)
class FindObligationPaymentCandidatesResult:
    candidates: list[PaymentCandidate]  # best first


@define(slots=True)
class FindObligationPaymentCandidatesUseCase:
    async def execute(
        self,
        command: FindObligationPaymentCandidatesCommand,
        uow: UnitOfWorkProtocol,
    ) -> FindObligationPaymentCandidatesResult:
        """The rows near the obligation's due date and amount that may pay
        it, from every account, transfers included, less the rows that pay
        another obligation. A row tagged with the obligation's loan ranks
        higher. Raise NotFoundError when the obligation does not exist."""
        async with uow:
            obligation = await require_by_id(
                uow.obligations.get_by_id, command.obligation_id, "Obligation"
            )
            others = await uow.obligations.get_by_asset_id(obligation.asset_id)
            loan = (
                await uow.loans.get_by_id(obligation.loan_id)
                if obligation.loan_id is not None
                else None
            )
            rows = await fetch_listed_rows(uow, candidate_window(obligation))
            return FindObligationPaymentCandidatesResult(
                candidates=find_payment_candidates(
                    obligation, rows, obligations=others, loan=loan
                )
            )
