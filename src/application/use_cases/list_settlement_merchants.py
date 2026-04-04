from attrs import define

from src.domain.entities.settlement_merchant import SettlementMerchant
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ListSettlementMerchantsCommand:
    """Parameterless -- exists for API uniformity."""


@define(frozen=True, slots=True)
class ListSettlementMerchantsResult:
    merchants: list[SettlementMerchant]


@define(slots=True)
class ListSettlementMerchantsUseCase:
    async def execute(
        self, _command: ListSettlementMerchantsCommand, uow: UnitOfWorkProtocol
    ) -> ListSettlementMerchantsResult:
        async with uow:
            merchants = await uow.settlement_merchants.get_all()
            return ListSettlementMerchantsResult(merchants=merchants)
