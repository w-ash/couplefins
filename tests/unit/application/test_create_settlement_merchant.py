import pytest

from src.application.use_cases.create_settlement_merchant import (
    CreateSettlementMerchantCommand,
    CreateSettlementMerchantUseCase,
)
from tests.fixtures.mocks import make_mock_uow


class TestCreateSettlementMerchant:
    async def test_creates_merchant(self) -> None:
        uow = make_mock_uow()
        uow.settlement_merchants.save.side_effect = lambda entity: entity

        command = CreateSettlementMerchantCommand(
            name="PayPal", merchant_pattern="paypal"
        )
        result = await CreateSettlementMerchantUseCase().execute(command, uow)

        assert result.merchant.name == "PayPal"
        assert result.merchant.merchant_pattern == "paypal"
        uow.commit.assert_called_once()

    async def test_short_pattern_raises(self) -> None:
        uow = make_mock_uow()
        uow.settlement_merchants.save.side_effect = lambda entity: entity

        command = CreateSettlementMerchantCommand(name="X", merchant_pattern="x")
        with pytest.raises(ValueError, match="at least 2"):
            await CreateSettlementMerchantUseCase().execute(command, uow)
