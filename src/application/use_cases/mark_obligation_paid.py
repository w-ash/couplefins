from uuid import UUID

import attrs
from attrs import define

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.domain.entities.obligation import Obligation
from src.domain.exceptions import ValidationError
from src.domain.obligations import paid_by_others
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class MarkObligationPaidCommand:
    """``transaction_id`` is the row that paid the obligation; None marks it
    unpaid again."""

    obligation_id: UUID
    transaction_id: UUID | None


@define(frozen=True, slots=True)
class MarkObligationPaidResult:
    obligation: Obligation


@define(slots=True)
class MarkObligationPaidUseCase:
    async def execute(
        self, command: MarkObligationPaidCommand, uow: UnitOfWorkProtocol
    ) -> MarkObligationPaidResult:
        """Link an obligation to the row that paid it, or unlink it.

        The row itself does not change, so no settlement, budget, or
        finalized month moves. Raise NotFoundError when the obligation or
        the row does not exist, and ValidationError when the row is not
        money out or already pays another obligation.
        """
        async with uow:
            obligation = await require_by_id(
                uow.obligations.get_by_id, command.obligation_id, "Obligation"
            )
            if command.transaction_id is not None:
                row = await require_by_id(
                    uow.transactions.get_by_id, command.transaction_id, "Transaction"
                )
                if row.amount >= 0:
                    raise ValidationError(
                        "A payment is money out; this row is money in"
                    )
                others = await uow.obligations.get_by_asset_id(obligation.asset_id)
                if row.id in paid_by_others(obligation, others):
                    raise ValidationError(
                        "This row already pays another obligation; unlink it there "
                        "first"
                    )
            saved = await uow.obligations.save(
                attrs.evolve(obligation, paid_by_transaction_id=command.transaction_id)
            )
            await uow.commit()
            return MarkObligationPaidResult(obligation=saved)
