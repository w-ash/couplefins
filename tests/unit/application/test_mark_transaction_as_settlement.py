from datetime import date

import pytest

from src.application.use_cases.mark_transaction_as_settlement import (
    MarkTransactionAsSettlementCommand,
    MarkTransactionAsSettlementUseCase,
)
from src.domain.exceptions import NotFoundError, PeriodFinalizedError
from tests.fixtures.factories import (
    make_reconciliation_period,
    make_settlement,
    make_transaction,
)
from tests.fixtures.mocks import make_mock_uow


class TestMarkTransactionAsSettlement:
    async def test_marks_transaction(self) -> None:
        tx = make_transaction(is_settlement=False)
        uow = make_mock_uow()
        uow.transactions.get_by_id.return_value = tx
        uow.transactions.update_mutable_fields.return_value = tx

        command = MarkTransactionAsSettlementCommand(transaction_id=tx.id)
        result = await MarkTransactionAsSettlementUseCase().execute(command, uow)

        assert result.is_settlement is True
        uow.transactions.update_mutable_fields.assert_called_once()
        uow.commit.assert_called_once()

    async def test_already_marked_skips_update(self) -> None:
        tx = make_transaction(is_settlement=True)
        uow = make_mock_uow()
        uow.transactions.get_by_id.return_value = tx

        command = MarkTransactionAsSettlementCommand(transaction_id=tx.id)
        result = await MarkTransactionAsSettlementUseCase().execute(command, uow)

        assert result.is_settlement is True
        uow.transactions.update_mutable_fields.assert_not_called()

    async def test_not_found_raises(self) -> None:
        uow = make_mock_uow()
        uow.transactions.get_by_id.return_value = None

        command = MarkTransactionAsSettlementCommand(
            transaction_id=make_transaction().id
        )
        with pytest.raises(NotFoundError):
            await MarkTransactionAsSettlementUseCase().execute(command, uow)

    async def test_links_to_settlement(self) -> None:
        tx = make_transaction(is_settlement=False)
        settlement = make_settlement()
        uow = make_mock_uow()
        uow.transactions.get_by_id.return_value = tx
        uow.settlements.get_by_id.return_value = settlement
        uow.transactions.update_mutable_fields.return_value = tx

        command = MarkTransactionAsSettlementCommand(
            transaction_id=tx.id,
            settlement_id=settlement.id,
        )
        result = await MarkTransactionAsSettlementUseCase().execute(command, uow)

        assert result.is_settlement is True
        uow.settlement_transaction_links.save_batch.assert_called_once()

    async def test_unmarks_transaction(self) -> None:
        tx = make_transaction(is_settlement=True)
        uow = make_mock_uow()
        uow.transactions.get_by_id.return_value = tx
        uow.transactions.update_mutable_fields.return_value = tx

        command = MarkTransactionAsSettlementCommand(
            transaction_id=tx.id, is_settlement=False
        )
        result = await MarkTransactionAsSettlementUseCase().execute(command, uow)

        assert result.is_settlement is False
        uow.transactions.update_mutable_fields.assert_called_once()
        uow.commit.assert_called_once()

    async def test_already_unmarked_skips_update(self) -> None:
        tx = make_transaction(is_settlement=False)
        uow = make_mock_uow()
        uow.transactions.get_by_id.return_value = tx

        command = MarkTransactionAsSettlementCommand(
            transaction_id=tx.id, is_settlement=False
        )
        result = await MarkTransactionAsSettlementUseCase().execute(command, uow)

        assert result.is_settlement is False
        uow.transactions.update_mutable_fields.assert_not_called()

    async def test_unmark_skips_settlement_link(self) -> None:
        tx = make_transaction(is_settlement=True)
        settlement = make_settlement()
        uow = make_mock_uow()
        uow.transactions.get_by_id.return_value = tx
        uow.transactions.update_mutable_fields.return_value = tx

        command = MarkTransactionAsSettlementCommand(
            transaction_id=tx.id,
            settlement_id=settlement.id,
            is_settlement=False,
        )
        result = await MarkTransactionAsSettlementUseCase().execute(command, uow)

        assert result.is_settlement is False
        uow.settlements.get_by_id.assert_not_called()
        uow.settlement_transaction_links.save_batch.assert_not_called()


async def test_finalized_transaction_month_raises() -> None:
    tx = make_transaction(date=date(2026, 1, 15), is_settlement=False)
    uow = make_mock_uow()
    uow.transactions.get_by_id.return_value = tx
    uow.reconciliation_periods.get_by_periods.return_value = [
        make_reconciliation_period(year=2026, month=1, is_finalized=True)
    ]

    command = MarkTransactionAsSettlementCommand(transaction_id=tx.id)
    with pytest.raises(PeriodFinalizedError):
        await MarkTransactionAsSettlementUseCase().execute(command, uow)
    uow.transactions.update_mutable_fields.assert_not_called()


async def test_finalized_settlement_month_raises_on_link() -> None:
    # Feb transaction linking into a Jan settlement while Jan is locked.
    tx = make_transaction(date=date(2026, 2, 10), is_settlement=False)
    settlement = make_settlement(year=2026, month=1)
    uow = make_mock_uow()
    uow.transactions.get_by_id.return_value = tx
    uow.settlements.get_by_id.return_value = settlement
    uow.reconciliation_periods.get_by_periods.return_value = [
        make_reconciliation_period(year=2026, month=1, is_finalized=True)
    ]

    command = MarkTransactionAsSettlementCommand(
        transaction_id=tx.id, settlement_id=settlement.id
    )
    with pytest.raises(PeriodFinalizedError):
        await MarkTransactionAsSettlementUseCase().execute(command, uow)
    uow.settlement_transaction_links.save_batch.assert_not_called()
