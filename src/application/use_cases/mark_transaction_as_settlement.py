import uuid

import attrs
from attrs import define

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.finalization import (
    assert_periods_not_finalized,
)
from src.domain.entities.settlement_transaction_link import SettlementTransactionLink
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class MarkTransactionAsSettlementCommand:
    transaction_id: uuid.UUID
    settlement_id: uuid.UUID | None = None
    is_settlement: bool = True


@define(frozen=True, slots=True)
class MarkTransactionAsSettlementResult:
    transaction_id: uuid.UUID
    is_settlement: bool


@define(slots=True)
class MarkTransactionAsSettlementUseCase:
    async def execute(
        self,
        command: MarkTransactionAsSettlementCommand,
        uow: UnitOfWorkProtocol,
    ) -> MarkTransactionAsSettlementResult:
        async with uow:
            tx = await require_by_id(
                uow.transactions.get_by_id, command.transaction_id, "Transaction"
            )

            # Flipping is_settlement changes the tx's month; a link also
            # changes the settlement's month (payment history).
            periods = {(tx.date.year, tx.date.month)}
            if command.is_settlement and command.settlement_id:
                settlement = await require_by_id(
                    uow.settlements.get_by_id, command.settlement_id, "Settlement"
                )
                periods.add((settlement.year, settlement.month))
            await assert_periods_not_finalized(uow, periods)

            if command.is_settlement and command.settlement_id:
                link = SettlementTransactionLink(
                    id=uuid.uuid4(),
                    settlement_id=command.settlement_id,
                    transaction_id=command.transaction_id,
                )
                await uow.settlement_transaction_links.save_batch([link])

            if tx.is_settlement != command.is_settlement:
                updated = attrs.evolve(tx, is_settlement=command.is_settlement)
                await uow.transactions.update_mutable_fields(updated)

            await uow.commit()
            return MarkTransactionAsSettlementResult(
                transaction_id=command.transaction_id,
                is_settlement=command.is_settlement,
            )
