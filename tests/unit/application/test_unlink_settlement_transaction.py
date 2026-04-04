import pytest

from src.application.use_cases.unlink_settlement_transaction import (
    UnlinkSettlementTransactionCommand,
    UnlinkSettlementTransactionUseCase,
)
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import (
    make_settlement,
    make_settlement_transaction_link,
    make_transaction,
)
from tests.fixtures.mocks import make_mock_uow


class TestUnlinkSettlementTransaction:
    async def test_unlinks_and_clears_is_settlement(self) -> None:
        settlement = make_settlement()
        tx = make_transaction(is_settlement=True)
        uow = make_mock_uow()
        uow.settlements.get_by_id.return_value = settlement
        uow.transactions.get_by_id.return_value = tx
        uow.settlement_transaction_links.delete_by_settlement_and_transaction.return_value = 1
        uow.settlement_transaction_links.get_by_transaction_id.return_value = []
        uow.transactions.update_mutable_fields.return_value = tx

        command = UnlinkSettlementTransactionCommand(
            settlement_id=settlement.id, transaction_id=tx.id
        )
        result = await UnlinkSettlementTransactionUseCase().execute(command, uow)

        assert result.unlinked is True
        uow.transactions.update_mutable_fields.assert_called_once()
        updated_tx = uow.transactions.update_mutable_fields.call_args.args[0]
        assert updated_tx.is_settlement is False

    async def test_keeps_is_settlement_when_other_links_remain(self) -> None:
        settlement = make_settlement()
        tx = make_transaction(is_settlement=True)
        remaining_link = make_settlement_transaction_link(transaction_id=tx.id)
        uow = make_mock_uow()
        uow.settlements.get_by_id.return_value = settlement
        uow.transactions.get_by_id.return_value = tx
        uow.settlement_transaction_links.delete_by_settlement_and_transaction.return_value = 1
        uow.settlement_transaction_links.get_by_transaction_id.return_value = [
            remaining_link
        ]

        command = UnlinkSettlementTransactionCommand(
            settlement_id=settlement.id, transaction_id=tx.id
        )
        result = await UnlinkSettlementTransactionUseCase().execute(command, uow)

        assert result.unlinked is True
        uow.transactions.update_mutable_fields.assert_not_called()

    async def test_settlement_not_found_raises(self) -> None:
        uow = make_mock_uow()
        uow.settlements.get_by_id.return_value = None

        command = UnlinkSettlementTransactionCommand(
            settlement_id=make_settlement().id,
            transaction_id=make_transaction().id,
        )
        with pytest.raises(NotFoundError):
            await UnlinkSettlementTransactionUseCase().execute(command, uow)

    async def test_transaction_not_found_raises(self) -> None:
        settlement = make_settlement()
        uow = make_mock_uow()
        uow.settlements.get_by_id.return_value = settlement
        uow.transactions.get_by_id.return_value = None

        command = UnlinkSettlementTransactionCommand(
            settlement_id=settlement.id,
            transaction_id=make_transaction().id,
        )
        with pytest.raises(NotFoundError):
            await UnlinkSettlementTransactionUseCase().execute(command, uow)
