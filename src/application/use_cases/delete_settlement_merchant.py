from uuid import UUID

from attrs import define

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class DeleteSettlementMerchantCommand:
    merchant_id: UUID


@define(frozen=True, slots=True)
class DeleteSettlementMerchantResult:
    deleted: bool


@define(slots=True)
class DeleteSettlementMerchantUseCase:
    async def execute(
        self, command: DeleteSettlementMerchantCommand, uow: UnitOfWorkProtocol
    ) -> DeleteSettlementMerchantResult:
        async with uow:
            await require_by_id(
                uow.settlement_merchants.get_by_id,
                command.merchant_id,
                "Settlement merchant",
            )
            deleted = await uow.settlement_merchants.delete(command.merchant_id)
            await uow.commit()
            return DeleteSettlementMerchantResult(deleted=deleted)
