import pytest

from src.application.use_cases.delete_settlement_merchant import (
    DeleteSettlementMerchantCommand,
    DeleteSettlementMerchantUseCase,
)
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import make_settlement_merchant
from tests.fixtures.mocks import make_mock_uow


class TestDeleteSettlementMerchant:
    async def test_deletes_merchant(self) -> None:
        merchant = make_settlement_merchant()
        uow = make_mock_uow()
        uow.settlement_merchants.get_by_id.return_value = merchant
        uow.settlement_merchants.delete.return_value = True

        command = DeleteSettlementMerchantCommand(merchant_id=merchant.id)
        result = await DeleteSettlementMerchantUseCase().execute(command, uow)

        assert result.deleted is True
        uow.settlement_merchants.delete.assert_called_once_with(merchant.id)
        uow.commit.assert_called_once()

    async def test_not_found_raises(self) -> None:
        uow = make_mock_uow()
        uow.settlement_merchants.get_by_id.return_value = None

        command = DeleteSettlementMerchantCommand(
            merchant_id=make_settlement_merchant().id
        )
        with pytest.raises(NotFoundError):
            await DeleteSettlementMerchantUseCase().execute(command, uow)
