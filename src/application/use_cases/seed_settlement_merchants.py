import uuid

from attrs import define
import structlog

from src.domain.entities.settlement_merchant import SettlementMerchant
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

logger = structlog.get_logger()

_DEFAULT_MERCHANTS = [
    ("Venmo", "venmo"),
    ("Zelle", "zelle"),
    ("Cash App", "cash app"),
]


@define(frozen=True, slots=True)
class SeedSettlementMerchantsCommand:
    """Parameterless -- exists for API uniformity."""


@define(frozen=True, slots=True)
class SeedSettlementMerchantsResult:
    merchants_created: int
    skipped: bool


@define(slots=True)
class SeedSettlementMerchantsUseCase:
    async def execute(
        self, _command: SeedSettlementMerchantsCommand, uow: UnitOfWorkProtocol
    ) -> SeedSettlementMerchantsResult:
        async with uow:
            existing_count = await uow.settlement_merchants.count()
            if existing_count > 0:
                logger.info(
                    "settlement_merchants_skipped", existing_count=existing_count
                )
                return SeedSettlementMerchantsResult(merchants_created=0, skipped=True)

            merchants = [
                SettlementMerchant(id=uuid.uuid4(), name=name, merchant_pattern=pattern)
                for name, pattern in _DEFAULT_MERCHANTS
            ]
            await uow.settlement_merchants.save_batch(merchants)
            await uow.commit()
            logger.info("settlement_merchants_seeded", count=len(merchants))
            return SeedSettlementMerchantsResult(
                merchants_created=len(merchants), skipped=False
            )


async def seed_settlement_merchants(
    uow: UnitOfWorkProtocol,
) -> SeedSettlementMerchantsResult:
    return await SeedSettlementMerchantsUseCase().execute(
        SeedSettlementMerchantsCommand(), uow
    )
