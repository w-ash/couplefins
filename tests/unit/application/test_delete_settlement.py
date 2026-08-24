from datetime import date

import pytest

from src.application.use_cases.delete_settlement import (
    DeleteSettlementCommand,
    DeleteSettlementUseCase,
)
from src.domain.exceptions import NotFoundError, PeriodFinalizedError
from tests.fixtures.factories import (
    make_reconciliation_period,
    make_settlement,
    make_settlement_transaction_link,
    make_transaction,
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

    async def test_delete_allowed_on_finalized_annotated_month(self) -> None:
        """Lock Month freezes transactions, not payments (v1.7.5): deleting
        a settlement with no linked transactions succeeds even when its
        annotated month is locked."""
        settlement = make_settlement()
        uow = make_mock_uow()
        uow.settlements.get_by_id.return_value = settlement
        uow.settlements.delete.return_value = True
        uow.settlement_transaction_links.get_by_settlement_ids.return_value = []
        uow.reconciliation_periods.get_by_periods.return_value = [
            make_reconciliation_period(year=2026, month=1, is_finalized=True)
        ]

        command = DeleteSettlementCommand(settlement_id=settlement.id)
        result = await DeleteSettlementUseCase().execute(command, uow)
        assert result.deleted is True
        uow.settlements.delete.assert_called_once_with(settlement.id)

    async def test_finalized_linked_transaction_month_raises(self) -> None:
        # Feb settlement linked to a Jan transaction; Jan is locked.
        settlement = make_settlement()
        tx = make_transaction(date=date(2026, 1, 30), is_settlement=True)
        link = make_settlement_transaction_link(
            settlement_id=settlement.id, transaction_id=tx.id
        )
        uow = make_mock_uow()
        uow.settlements.get_by_id.return_value = settlement
        uow.settlement_transaction_links.get_by_settlement_ids.return_value = [link]
        uow.transactions.get_by_ids.return_value = [tx]
        uow.reconciliation_periods.get_by_periods.return_value = [
            make_reconciliation_period(year=2026, month=1, is_finalized=True)
        ]

        command = DeleteSettlementCommand(settlement_id=settlement.id)
        with pytest.raises(PeriodFinalizedError):
            await DeleteSettlementUseCase().execute(command, uow)
        uow.transactions.update_mutable_fields.assert_not_called()
        uow.settlements.delete.assert_not_called()

    async def test_does_not_unmark_linked_transactions(self) -> None:
        settlement = make_settlement()
        uow = make_mock_uow()
        uow.settlements.get_by_id.return_value = settlement
        uow.settlements.delete.return_value = True

        command = DeleteSettlementCommand(settlement_id=settlement.id)
        await DeleteSettlementUseCase().execute(command, uow)
        uow.transactions.update_mutable_fields.assert_not_called()
