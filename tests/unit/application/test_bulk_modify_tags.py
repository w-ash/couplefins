from datetime import UTC, datetime
import uuid

import pytest

from src.application.use_cases.bulk_modify_tags import (
    BulkModifyTagsCommand,
    BulkModifyTagsUseCase,
    TagAction,
)
from src.domain.exceptions import NotFoundError, PeriodFinalizedError, ValidationError
from tests.fixtures.factories import make_reconciliation_period, make_transaction
from tests.fixtures.mocks import make_mock_uow


def _make_command(
    transaction_ids: list[uuid.UUID] | None = None,
    action: TagAction = TagAction.ADD,
    tags: list[str] | None = None,
) -> BulkModifyTagsCommand:
    return BulkModifyTagsCommand(
        transaction_ids=transaction_ids
        if transaction_ids is not None
        else [uuid.uuid4()],
        action=action,
        tags=tags if tags is not None else ["new-tag"],
    )


async def test_adds_tags_to_transactions() -> None:
    uow = make_mock_uow()
    tx1 = make_transaction(tags=("shared",))
    tx2 = make_transaction(tags=("shared", "food"))
    uow.transactions.get_by_ids.return_value = [tx1, tx2]

    command = _make_command(
        transaction_ids=[tx1.id, tx2.id],
        action=TagAction.ADD,
        tags=["dinner"],
    )
    result = await BulkModifyTagsUseCase().execute(command, uow)

    assert result.updated_count == 2
    calls = uow.transactions.update_mutable_fields.call_args_list
    assert calls[0][0][0].tags == ("shared", "dinner")
    assert calls[1][0][0].tags == ("shared", "food", "dinner")
    uow.commit.assert_called_once()


async def test_add_deduplicates_existing_tags() -> None:
    uow = make_mock_uow()
    tx = make_transaction(tags=("shared", "dinner"))
    uow.transactions.get_by_ids.return_value = [tx]

    command = _make_command(
        transaction_ids=[tx.id],
        action=TagAction.ADD,
        tags=["dinner", "new-tag"],
    )
    result = await BulkModifyTagsUseCase().execute(command, uow)

    assert result.updated_count == 1
    updated = uow.transactions.update_mutable_fields.call_args[0][0]
    assert updated.tags == ("shared", "dinner", "new-tag")


async def test_add_skips_when_all_tags_exist() -> None:
    uow = make_mock_uow()
    tx = make_transaction(tags=("shared", "dinner"))
    uow.transactions.get_by_ids.return_value = [tx]

    command = _make_command(
        transaction_ids=[tx.id],
        action=TagAction.ADD,
        tags=["shared", "dinner"],
    )
    result = await BulkModifyTagsUseCase().execute(command, uow)

    assert result.updated_count == 0
    uow.transactions.update_mutable_fields.assert_not_called()


async def test_removes_tags_from_transactions() -> None:
    uow = make_mock_uow()
    tx1 = make_transaction(tags=("shared", "dinner", "food"))
    tx2 = make_transaction(tags=("shared", "dinner"))
    uow.transactions.get_by_ids.return_value = [tx1, tx2]

    command = _make_command(
        transaction_ids=[tx1.id, tx2.id],
        action=TagAction.REMOVE,
        tags=["dinner"],
    )
    result = await BulkModifyTagsUseCase().execute(command, uow)

    assert result.updated_count == 2
    calls = uow.transactions.update_mutable_fields.call_args_list
    assert calls[0][0][0].tags == ("shared", "food")
    assert calls[1][0][0].tags == ("shared",)


async def test_remove_skips_when_tags_not_present() -> None:
    uow = make_mock_uow()
    tx = make_transaction(tags=("shared",))
    uow.transactions.get_by_ids.return_value = [tx]

    command = _make_command(
        transaction_ids=[tx.id],
        action=TagAction.REMOVE,
        tags=["nonexistent"],
    )
    result = await BulkModifyTagsUseCase().execute(command, uow)

    assert result.updated_count == 0
    uow.transactions.update_mutable_fields.assert_not_called()


async def test_creates_audit_edits_for_tag_changes() -> None:
    uow = make_mock_uow()
    tx = make_transaction(tags=("shared",))
    uow.transactions.get_by_ids.return_value = [tx]

    command = _make_command(
        transaction_ids=[tx.id],
        action=TagAction.ADD,
        tags=["dinner"],
    )
    await BulkModifyTagsUseCase().execute(command, uow)

    edits = uow.transaction_edits.save_batch.call_args[0][0]
    assert len(edits) == 1
    assert edits[0].field_name == "tags"
    assert edits[0].old_value == "shared"
    assert edits[0].new_value == "shared,dinner"
    assert edits[0].transaction_id == tx.id


async def test_rejects_empty_transaction_ids() -> None:
    uow = make_mock_uow()
    command = _make_command(transaction_ids=[])

    with pytest.raises(ValidationError, match="At least one transaction ID"):
        await BulkModifyTagsUseCase().execute(command, uow)


async def test_rejects_empty_tags() -> None:
    uow = make_mock_uow()
    command = _make_command(tags=[])

    with pytest.raises(ValidationError, match="At least one tag"):
        await BulkModifyTagsUseCase().execute(command, uow)


async def test_raises_not_found_for_missing_transaction() -> None:
    uow = make_mock_uow()
    uow.transactions.get_by_ids.return_value = []
    missing_id = uuid.uuid4()
    command = _make_command(transaction_ids=[missing_id])

    with pytest.raises(NotFoundError, match=str(missing_id)):
        await BulkModifyTagsUseCase().execute(command, uow)


async def test_rejects_update_to_finalized_period() -> None:
    uow = make_mock_uow()
    tx = make_transaction()
    uow.transactions.get_by_ids.return_value = [tx]
    uow.reconciliation_periods.get_by_period.return_value = make_reconciliation_period(
        year=tx.date.year,
        month=tx.date.month,
        is_finalized=True,
        finalized_at=datetime.now(UTC),
    )
    command = _make_command(transaction_ids=[tx.id], tags=["new-tag"])

    with pytest.raises(PeriodFinalizedError):
        await BulkModifyTagsUseCase().execute(command, uow)


async def test_preserves_tag_order_on_add() -> None:
    uow = make_mock_uow()
    tx = make_transaction(tags=("c", "a", "b"))
    uow.transactions.get_by_ids.return_value = [tx]

    command = _make_command(
        transaction_ids=[tx.id],
        action=TagAction.ADD,
        tags=["d"],
    )
    await BulkModifyTagsUseCase().execute(command, uow)

    updated = uow.transactions.update_mutable_fields.call_args[0][0]
    assert updated.tags == ("c", "a", "b", "d")


async def test_preserves_tag_order_on_remove() -> None:
    uow = make_mock_uow()
    tx = make_transaction(tags=("c", "a", "b", "d"))
    uow.transactions.get_by_ids.return_value = [tx]

    command = _make_command(
        transaction_ids=[tx.id],
        action=TagAction.REMOVE,
        tags=["a", "d"],
    )
    await BulkModifyTagsUseCase().execute(command, uow)

    updated = uow.transactions.update_mutable_fields.call_args[0][0]
    assert updated.tags == ("c", "b")
