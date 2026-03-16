import uuid

from attrs import define

from src.application.use_cases._shared.finalization import assert_period_not_finalized
from src.domain.exceptions import NotFoundError
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
            settlement = await uow.settlements.get_by_id(command.settlement_id)
            if not settlement:
                raise NotFoundError(f"Settlement {command.settlement_id} not found")

            await assert_period_not_finalized(uow, settlement.year, settlement.month)

            await uow.settlement_transaction_links.delete_by_settlement_id(
                settlement.id
            )
            await uow.settlements.delete(settlement.id)

            await uow.commit()
            return DeleteSettlementResult(deleted=True)
