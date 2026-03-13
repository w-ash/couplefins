from datetime import UTC, datetime
from decimal import Decimal
import uuid

import pytest

from src.application.use_cases.update_transaction_splits import (
    SplitEntry,
    UpdateTransactionSplitsCommand,
    UpdateTransactionSplitsUseCase,
)
from src.domain.exceptions import NotFoundError, PeriodFinalizedError, ValidationError
from tests.fixtures.factories import make_reconciliation_period, make_transaction
from tests.fixtures.mocks import make_mock_uow


def _make_command(
    splits: list[SplitEntry] | None = None,
) -> UpdateTransactionSplitsCommand:
    return UpdateTransactionSplitsCommand(
        splits=splits
        if splits is not None
        else [SplitEntry(transaction_id=uuid.uuid4(), payer_percentage=70)]
    )


async def test_updates_single_transaction_split() -> None:
    uow = make_mock_uow()
    tx = make_transaction(payer_percentage=50)
    uow.transactions.get_by_ids.return_value = [tx]
    command = _make_command([SplitEntry(transaction_id=tx.id, payer_percentage=70)])

    result = await UpdateTransactionSplitsUseCase().execute(command, uow)

    assert result.updated_count == 1
    uow.transactions.update_mutable_fields.assert_called_once()
    updated_tx = uow.transactions.update_mutable_fields.call_args[0][0]
    assert updated_tx.payer_percentage == 70
    assert updated_tx.id == tx.id
    uow.commit.assert_called_once()


async def test_updates_multiple_transactions_in_bulk() -> None:
    uow = make_mock_uow()
    tx1 = make_transaction(payer_percentage=50)
    tx2 = make_transaction(payer_percentage=50, amount=Decimal("-100.00"))

    uow.transactions.get_by_ids.return_value = [tx1, tx2]
    command = _make_command([
        SplitEntry(transaction_id=tx1.id, payer_percentage=60),
        SplitEntry(transaction_id=tx2.id, payer_percentage=80),
    ])

    result = await UpdateTransactionSplitsUseCase().execute(command, uow)

    assert result.updated_count == 2
    assert uow.transactions.update_mutable_fields.call_count == 2
    uow.commit.assert_called_once()


async def test_rejects_empty_splits() -> None:
    uow = make_mock_uow()
    command = _make_command(splits=[])

    with pytest.raises(ValidationError, match="At least one"):
        await UpdateTransactionSplitsUseCase().execute(command, uow)


async def test_rejects_invalid_payer_percentage() -> None:
    uow = make_mock_uow()
    command = _make_command([
        SplitEntry(transaction_id=uuid.uuid4(), payer_percentage=150)
    ])

    with pytest.raises(ValidationError, match="payer_percentage"):
        await UpdateTransactionSplitsUseCase().execute(command, uow)


async def test_rejects_negative_payer_percentage() -> None:
    uow = make_mock_uow()
    command = _make_command([
        SplitEntry(transaction_id=uuid.uuid4(), payer_percentage=-1)
    ])

    with pytest.raises(ValidationError, match="payer_percentage"):
        await UpdateTransactionSplitsUseCase().execute(command, uow)


async def test_raises_not_found_for_missing_transaction() -> None:
    uow = make_mock_uow()
    uow.transactions.get_by_ids.return_value = []
    missing_id = uuid.uuid4()
    command = _make_command([
        SplitEntry(transaction_id=missing_id, payer_percentage=70)
    ])

    with pytest.raises(NotFoundError, match=str(missing_id)):
        await UpdateTransactionSplitsUseCase().execute(command, uow)


async def test_rejects_update_to_finalized_period() -> None:
    uow = make_mock_uow()
    tx = make_transaction(payer_percentage=50)
    uow.transactions.get_by_ids.return_value = [tx]
    uow.reconciliation_periods.get_by_period.return_value = make_reconciliation_period(
        year=tx.date.year,
        month=tx.date.month,
        is_finalized=True,
        finalized_at=datetime.now(UTC),
    )
    command = _make_command([SplitEntry(transaction_id=tx.id, payer_percentage=70)])

    with pytest.raises(PeriodFinalizedError):
        await UpdateTransactionSplitsUseCase().execute(command, uow)


async def test_allows_boundary_percentages() -> None:
    uow = make_mock_uow()
    tx0 = make_transaction(payer_percentage=50)
    tx100 = make_transaction(payer_percentage=50)

    uow.transactions.get_by_ids.return_value = [tx0, tx100]
    command = _make_command([
        SplitEntry(transaction_id=tx0.id, payer_percentage=0),
        SplitEntry(transaction_id=tx100.id, payer_percentage=100),
    ])

    result = await UpdateTransactionSplitsUseCase().execute(command, uow)

    assert result.updated_count == 2
    calls = uow.transactions.update_mutable_fields.call_args_list
    percentages = {call[0][0].payer_percentage for call in calls}
    assert percentages == {0, 100}


async def test_preserves_other_transaction_fields() -> None:
    uow = make_mock_uow()
    tx = make_transaction(
        merchant="Original Merchant",
        category="Dining Out",
        notes="Test notes",
        tags=("shared", "s50"),
        payer_percentage=50,
    )
    uow.transactions.get_by_ids.return_value = [tx]
    command = _make_command([SplitEntry(transaction_id=tx.id, payer_percentage=70)])

    await UpdateTransactionSplitsUseCase().execute(command, uow)

    updated_tx = uow.transactions.update_mutable_fields.call_args[0][0]
    assert updated_tx.merchant == "Original Merchant"
    assert updated_tx.category == "Dining Out"
    assert updated_tx.notes == "Test notes"
    assert updated_tx.tags == ("shared", "s50")
    assert updated_tx.payer_percentage == 70
