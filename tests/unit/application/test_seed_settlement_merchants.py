from src.application.use_cases.seed_settlement_merchants import (
    SeedSettlementMerchantsCommand,
    SeedSettlementMerchantsUseCase,
)
from tests.fixtures.mocks import make_mock_uow


class TestSeedSettlementMerchants:
    async def test_seeds_defaults(self) -> None:
        uow = make_mock_uow()
        uow.settlement_merchants.count.return_value = 0
        uow.settlement_merchants.save_batch.return_value = []

        result = await SeedSettlementMerchantsUseCase().execute(
            SeedSettlementMerchantsCommand(), uow
        )

        assert result.merchants_created == 3
        assert result.skipped is False
        uow.settlement_merchants.save_batch.assert_called_once()
        saved = uow.settlement_merchants.save_batch.call_args.args[0]
        names = {m.name for m in saved}
        assert names == {"Venmo", "Zelle", "Cash App"}

    async def test_skips_when_exists(self) -> None:
        uow = make_mock_uow()
        uow.settlement_merchants.count.return_value = 3

        result = await SeedSettlementMerchantsUseCase().execute(
            SeedSettlementMerchantsCommand(), uow
        )

        assert result.merchants_created == 0
        assert result.skipped is True
        uow.settlement_merchants.save_batch.assert_not_called()
