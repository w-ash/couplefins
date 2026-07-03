from uuid import UUID

import attrs
from attrs import define

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.finalization import (
    assert_periods_not_finalized,
)
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UnlinkSettlementTransactionCommand:
    settlement_id: UUID
    transaction_id: UUID


@define(frozen=True, slots=True)
class UnlinkSettlementTransactionResult:
    unlinked: bool


@define(slots=True)
class UnlinkSettlementTransactionUseCase:
    async def execute(
        self,
        command: UnlinkSettlementTransactionCommand,
        uow: UnitOfWorkProtocol,
    ) -> UnlinkSettlementTransactionResult:
        async with uow:
            settlement = await require_by_id(
                uow.settlements.get_by_id, command.settlement_id, "Settlement"
            )
            tx = await require_by_id(
                uow.transactions.get_by_id, command.transaction_id, "Transaction"
            )

            await assert_periods_not_finalized(
                uow,
                {
                    (settlement.year, settlement.month),
                    (tx.date.year, tx.date.month),
                },
            )

            deleted = await uow.settlement_transaction_links.delete_by_settlement_and_transaction(
                command.settlement_id, command.transaction_id
            )

            if deleted > 0:
                remaining = (
                    await uow.settlement_transaction_links.get_by_transaction_id(
                        command.transaction_id
                    )
                )
                if not remaining and tx.is_settlement:
                    updated = attrs.evolve(tx, is_settlement=False)
                    await uow.transactions.update_mutable_fields(updated)

            await uow.commit()
            return UnlinkSettlementTransactionResult(unlinked=deleted > 0)
