import uuid

import attrs
from attrs import define

from src.domain.entities.settlement_transaction_link import SettlementTransactionLink
from src.domain.exceptions import NotFoundError
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
            tx = await uow.transactions.get_by_id(command.transaction_id)
            if not tx:
                raise NotFoundError(f"Transaction {command.transaction_id} not found")

            if command.is_settlement and command.settlement_id:
                settlement = await uow.settlements.get_by_id(command.settlement_id)
                if not settlement:
                    raise NotFoundError(f"Settlement {command.settlement_id} not found")
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
