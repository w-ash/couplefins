import uuid

from attrs import define, evolve

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.finalization import (
    assert_periods_not_finalized,
)
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class DeleteSettlementCommand:
    settlement_id: uuid.UUID


@define(frozen=True, slots=True)
class DeleteSettlementResult:
    deleted: bool


@define(slots=True)
class DeleteSettlementUseCase:
    async def execute(
        self, command: DeleteSettlementCommand, uow: UnitOfWorkProtocol
    ) -> DeleteSettlementResult:
        async with uow:
            settlement = await require_by_id(
                uow.settlements.get_by_id, command.settlement_id, "Settlement"
            )

            links = await uow.settlement_transaction_links.get_by_settlement_ids([
                settlement.id
            ])
            linked_txs = (
                await uow.transactions.get_by_ids([
                    link.transaction_id for link in links
                ])
                if links
                else []
            )

            # Lock Month freezes transactions, not payments: deleting the
            # settlement record is always allowed, but unlinking flips
            # is_settlement in each linked tx's own month (cross-month links
            # exist via the candidate window).
            await assert_periods_not_finalized(
                uow, {(tx.date.year, tx.date.month) for tx in linked_txs}
            )

            for tx in linked_txs:
                if tx.is_settlement:
                    await uow.transactions.update_mutable_fields(
                        evolve(tx, is_settlement=False)
                    )

            await uow.settlement_transaction_links.delete_by_settlement_id(
                settlement.id
            )
            await uow.settlements.delete(settlement.id)

            await uow.commit()
            return DeleteSettlementResult(deleted=True)
