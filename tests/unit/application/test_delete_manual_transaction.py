"""US-HOUSE-11: deleting a recorded credit removes it; an imported row is
never deleted here."""

from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.delete_manual_transaction import (
    DeleteManualTransactionCommand,
    DeleteManualTransactionUseCase,
)
from src.domain.entities.transaction import Transaction
from src.domain.entities.upload import MANUAL_IMPORTER
from src.domain.exceptions import (
    NotFoundError,
    PeriodFinalizedError,
    ValidationError,
)
from tests.fixtures.factories import (
    BOB,
    make_manual_transaction,
    make_reconciliation_period,
    make_settlement_transaction_link,
    make_transaction,
    make_upload,
)
from tests.fixtures.mocks import make_mock_uow


def _uow(tx: Transaction, importer: str = MANUAL_IMPORTER) -> AsyncMock:
    uow = make_mock_uow()
    uow.transactions.get_by_id.return_value = tx
    uow.uploads.get_by_id.return_value = make_upload(
        id=tx.upload_id, person_id=BOB.id, importer=importer
    )
    return uow


async def _delete(uow: AsyncMock, tx: Transaction) -> bool:
    command = DeleteManualTransactionCommand(transaction_id=tx.id)
    result = await DeleteManualTransactionUseCase().execute(command, uow)
    return result.deleted


class TestDeleteManualTransaction:
    async def test_deletes_the_row_with_its_edits_and_links(self) -> None:
        tx = make_manual_transaction()
        uow = _uow(tx)
        uow.settlement_transaction_links.get_by_transaction_ids.return_value = [
            make_settlement_transaction_link(transaction_id=tx.id)
        ]

        assert await _delete(uow, tx) is True
        uow.transaction_edits.delete_by_transaction_ids.assert_awaited_once_with([
            tx.id
        ])
        uow.settlement_transaction_links.delete_by_transaction_ids.assert_awaited_once_with([
            tx.id
        ])
        uow.transactions.delete_by_ids.assert_awaited_once_with([tx.id])
        uow.commit.assert_awaited_once()

    async def test_an_imported_row_is_refused(self) -> None:
        tx = make_transaction(joint=True)
        uow = _uow(tx, importer="monarch_csv")

        with pytest.raises(ValidationError, match="hand-entered"):
            await _delete(uow, tx)
        uow.transactions.delete_by_ids.assert_not_called()

    async def test_a_row_whose_upload_is_gone_is_refused(self) -> None:
        tx = make_manual_transaction()
        uow = _uow(tx)
        uow.uploads.get_by_id.return_value = None

        with pytest.raises(ValidationError):
            await _delete(uow, tx)

    async def test_a_finalized_month_is_refused(self) -> None:
        tx = make_manual_transaction()
        uow = _uow(tx)
        uow.reconciliation_periods.get_by_periods.return_value = [
            make_reconciliation_period(
                year=tx.date.year, month=tx.date.month, is_finalized=True
            )
        ]

        with pytest.raises(PeriodFinalizedError):
            await _delete(uow, tx)
        uow.transactions.delete_by_ids.assert_not_called()

    async def test_a_missing_row_is_not_found(self) -> None:
        tx = make_manual_transaction()
        uow = make_mock_uow()
        uow.transactions.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await _delete(uow, tx)
