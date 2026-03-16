import pytest

from src.application.use_cases.delete_settlement import (
    DeleteSettlementCommand,
    DeleteSettlementUseCase,
)
from src.domain.exceptions import NotFoundError, PeriodFinalizedError
from tests.fixtures.factories import (
    make_reconciliation_period,
    make_settlement,
)
from tests.fixtures.mocks import make_mock_uow


class TestDeleteSettlement:
    async def test_deletes_settlement(self) -> None:
        settlement = make_settlement()
        uow = make_mock_uow()
        uow.settlements.get_by_id.return_value = settlement
        uow.settlements.delete.return_value = True

        command = DeleteSettlementCommand(settlement_id=settlement.id)
        result = await DeleteSettlementUseCase().execute(command, uow)
        assert result.deleted is True
        uow.settlement_transaction_links.delete_by_settlement_id.assert_called_once_with(
            settlement.id
        )
        uow.settlements.delete.assert_called_once_with(settlement.id)
        uow.commit.assert_called_once()

    async def test_not_found_raises(self) -> None:
        uow = make_mock_uow()
        uow.settlements.get_by_id.return_value = None

        command = DeleteSettlementCommand(settlement_id=make_settlement().id)
        with pytest.raises(NotFoundError):
            await DeleteSettlementUseCase().execute(command, uow)

    async def test_finalized_period_raises(self) -> None:
        settlement = make_settlement(year=2026, month=1)
        uow = make_mock_uow()
        uow.settlements.get_by_id.return_value = settlement
        uow.reconciliation_periods.get_by_period.return_value = (
            make_reconciliation_period(year=2026, month=1, is_finalized=True)
        )

        command = DeleteSettlementCommand(settlement_id=settlement.id)
        with pytest.raises(PeriodFinalizedError):
            await DeleteSettlementUseCase().execute(command, uow)

    async def test_does_not_unmark_linked_transactions(self) -> None:
        settlement = make_settlement()
        uow = make_mock_uow()
        uow.settlements.get_by_id.return_value = settlement
        uow.settlements.delete.return_value = True

        command = DeleteSettlementCommand(settlement_id=settlement.id)
        await DeleteSettlementUseCase().execute(command, uow)
        uow.transactions.update_mutable_fields.assert_not_called()
