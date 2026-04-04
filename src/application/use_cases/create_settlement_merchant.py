import uuid

from attrs import define, field

from src.application.use_cases._shared.command_validators import non_empty_string
from src.domain.entities.settlement_merchant import SettlementMerchant
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class CreateSettlementMerchantCommand:
    name: str = field(validator=non_empty_string)
    merchant_pattern: str = field(validator=non_empty_string)


@define(frozen=True, slots=True)
class CreateSettlementMerchantResult:
    merchant: SettlementMerchant


@define(slots=True)
class CreateSettlementMerchantUseCase:
    async def execute(
        self, command: CreateSettlementMerchantCommand, uow: UnitOfWorkProtocol
    ) -> CreateSettlementMerchantResult:
        async with uow:
            merchant = SettlementMerchant(
                id=uuid.uuid4(),
                name=command.name,
                merchant_pattern=command.merchant_pattern,
            )
            saved = await uow.settlement_merchants.save(merchant)
            await uow.commit()
            return CreateSettlementMerchantResult(merchant=saved)
