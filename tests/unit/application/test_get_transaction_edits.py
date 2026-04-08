import uuid

import pytest

from src.application.use_cases.get_transaction_edits import (
    GetTransactionEditsCommand,
    GetTransactionEditsUseCase,
)
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import (
    make_transaction,
    make_transaction_edit,
    make_upload,
)
from tests.fixtures.mocks import make_mock_uow


def _setup_uow_with_upload(uow, *, tx=None, upload=None):
    """Wire up a mock UoW with a transaction and its upload."""
    if tx is None:
        tx = make_transaction()
    if upload is None:
        upload = make_upload(id=tx.upload_id, person_id=uuid.uuid4())
    uow.transactions.get_by_id.return_value = tx
    uow.uploads.get_by_id.return_value = upload
    return tx, upload


async def test_returns_edits_for_transaction() -> None:
    uow = make_mock_uow()
    tx, _ = _setup_uow_with_upload(uow)
    edit1 = make_transaction_edit(transaction_id=tx.id, field_name="category")
    edit2 = make_transaction_edit(transaction_id=tx.id, field_name="tags")
    uow.transaction_edits.get_by_transaction_id.return_value = [edit1, edit2]

    command = GetTransactionEditsCommand(transaction_id=tx.id)
    result = await GetTransactionEditsUseCase().execute(command, uow)

    assert len(result.edits) == 2
    uow.transaction_edits.get_by_transaction_id.assert_called_once_with(tx.id)


async def test_returns_empty_when_no_edits() -> None:
    uow = make_mock_uow()
    tx, _ = _setup_uow_with_upload(uow)
    uow.transaction_edits.get_by_transaction_id.return_value = []

    command = GetTransactionEditsCommand(transaction_id=tx.id)
    result = await GetTransactionEditsUseCase().execute(command, uow)

    assert result.edits == []
    assert result.import_event is not None


async def test_raises_not_found_for_missing_transaction() -> None:
    uow = make_mock_uow()
    uow.transactions.get_by_id.return_value = None
    missing_id = uuid.uuid4()

    command = GetTransactionEditsCommand(transaction_id=missing_id)
    with pytest.raises(NotFoundError, match=str(missing_id)):
        await GetTransactionEditsUseCase().execute(command, uow)


async def test_returns_edited_by_person_id() -> None:
    uow = make_mock_uow()
    tx, _ = _setup_uow_with_upload(uow)
    person_id = uuid.uuid4()
    edit = make_transaction_edit(transaction_id=tx.id, edited_by_person_id=person_id)
    uow.transaction_edits.get_by_transaction_id.return_value = [edit]

    command = GetTransactionEditsCommand(transaction_id=tx.id)
    result = await GetTransactionEditsUseCase().execute(command, uow)

    assert result.edits[0].edited_by_person_id == person_id


async def test_returns_none_edited_by_for_historical_edits() -> None:
    uow = make_mock_uow()
    tx, _ = _setup_uow_with_upload(uow)
    edit = make_transaction_edit(transaction_id=tx.id)
    uow.transaction_edits.get_by_transaction_id.return_value = [edit]

    command = GetTransactionEditsCommand(transaction_id=tx.id)
    result = await GetTransactionEditsUseCase().execute(command, uow)

    assert result.edits[0].edited_by_person_id is None


async def test_returns_import_event_from_upload() -> None:
    uow = make_mock_uow()
    person_id = uuid.uuid4()
    upload = make_upload(person_id=person_id)
    tx, _ = _setup_uow_with_upload(
        uow, tx=make_transaction(upload_id=upload.id), upload=upload
    )
    uow.transaction_edits.get_by_transaction_id.return_value = []

    command = GetTransactionEditsCommand(transaction_id=tx.id)
    result = await GetTransactionEditsUseCase().execute(command, uow)

    assert result.import_event is not None
    assert result.import_event.person_id == person_id
    assert result.import_event.imported_at == upload.uploaded_at
    uow.uploads.get_by_id.assert_called_once_with(tx.upload_id)


async def test_returns_none_import_event_when_upload_missing() -> None:
    uow = make_mock_uow()
    tx = make_transaction()
    uow.transactions.get_by_id.return_value = tx
    uow.uploads.get_by_id.return_value = None
    uow.transaction_edits.get_by_transaction_id.return_value = []

    command = GetTransactionEditsCommand(transaction_id=tx.id)
    result = await GetTransactionEditsUseCase().execute(command, uow)

    assert result.import_event is None
