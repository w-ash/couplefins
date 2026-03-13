import uuid

import pytest

from src.application.use_cases.get_transaction_edits import (
    GetTransactionEditsCommand,
    GetTransactionEditsUseCase,
)
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import make_transaction, make_transaction_edit
from tests.fixtures.mocks import make_mock_uow


async def test_returns_edits_for_transaction() -> None:
    uow = make_mock_uow()
    tx = make_transaction()
    edit1 = make_transaction_edit(transaction_id=tx.id, field_name="category")
    edit2 = make_transaction_edit(transaction_id=tx.id, field_name="tags")
    uow.transactions.get_by_id.return_value = tx
    uow.transaction_edits.get_by_transaction_id.return_value = [edit1, edit2]

    command = GetTransactionEditsCommand(transaction_id=tx.id)
    result = await GetTransactionEditsUseCase().execute(command, uow)

    assert len(result.edits) == 2
    uow.transaction_edits.get_by_transaction_id.assert_called_once_with(tx.id)


async def test_returns_empty_when_no_edits() -> None:
    uow = make_mock_uow()
    tx = make_transaction()
    uow.transactions.get_by_id.return_value = tx
    uow.transaction_edits.get_by_transaction_id.return_value = []

    command = GetTransactionEditsCommand(transaction_id=tx.id)
    result = await GetTransactionEditsUseCase().execute(command, uow)

    assert result.edits == []


async def test_raises_not_found_for_missing_transaction() -> None:
    uow = make_mock_uow()
    uow.transactions.get_by_id.return_value = None
    missing_id = uuid.uuid4()

    command = GetTransactionEditsCommand(transaction_id=missing_id)
    with pytest.raises(NotFoundError, match=str(missing_id)):
        await GetTransactionEditsUseCase().execute(command, uow)
