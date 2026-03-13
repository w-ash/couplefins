from datetime import UTC, date, datetime
from decimal import Decimal
import uuid

import pytest

from src.application.use_cases.update_transaction import (
    UpdateTransactionCommand,
    UpdateTransactionUseCase,
)
from src.domain.exceptions import NotFoundError, PeriodFinalizedError, ValidationError
from tests.fixtures.factories import make_reconciliation_period, make_transaction
from tests.fixtures.mocks import make_mock_uow


async def test_single_field_update_creates_one_edit() -> None:
    uow = make_mock_uow()
    tx = make_transaction(category="Dining Out")
    uow.transactions.get_by_id.return_value = tx
    command = UpdateTransactionCommand(
        transaction_id=tx.id,
        category="Fast Food",
    )

    result = await UpdateTransactionUseCase().execute(command, uow)

    assert len(result.edits) == 1
    assert result.edits[0].field_name == "category"
    assert result.edits[0].old_value == "Dining Out"
    assert result.edits[0].new_value == "Fast Food"
    assert result.transaction.category == "Fast Food"
    uow.transaction_edits.save_batch.assert_called_once()
    uow.transactions.update_all_fields.assert_called_once()
    uow.commit.assert_called_once()


async def test_multi_field_update_creates_multiple_edits() -> None:
    uow = make_mock_uow()
    tx = make_transaction(category="Dining Out", tags=("shared",))
    uow.transactions.get_by_id.return_value = tx
    command = UpdateTransactionCommand(
        transaction_id=tx.id,
        category="Fast Food",
        tags=("shared", "s70"),
    )

    result = await UpdateTransactionUseCase().execute(command, uow)

    assert len(result.edits) == 2
    field_names = {e.field_name for e in result.edits}
    assert field_names == {"category", "tags"}


async def test_noop_when_values_unchanged() -> None:
    uow = make_mock_uow()
    tx = make_transaction(category="Dining Out")
    uow.transactions.get_by_id.return_value = tx
    command = UpdateTransactionCommand(
        transaction_id=tx.id,
        category="Dining Out",
    )

    result = await UpdateTransactionUseCase().execute(command, uow)

    assert len(result.edits) == 0
    uow.transaction_edits.save_batch.assert_not_called()
    uow.transactions.update_all_fields.assert_not_called()
    uow.commit.assert_not_called()


async def test_finalization_guard_on_current_period() -> None:
    uow = make_mock_uow()
    tx = make_transaction()
    uow.transactions.get_by_id.return_value = tx
    uow.reconciliation_periods.get_by_period.return_value = make_reconciliation_period(
        year=tx.date.year,
        month=tx.date.month,
        is_finalized=True,
        finalized_at=datetime.now(UTC),
    )
    command = UpdateTransactionCommand(transaction_id=tx.id, category="New")

    with pytest.raises(PeriodFinalizedError):
        await UpdateTransactionUseCase().execute(command, uow)


async def test_finalization_guard_on_new_period_when_date_changes() -> None:
    uow = make_mock_uow()
    tx = make_transaction(date=date(2026, 1, 15))
    uow.transactions.get_by_id.return_value = tx
    new_date = date(2026, 3, 10)

    def fake_get_by_period(year: int, month: int):
        if year == 2026 and month == 3:
            return make_reconciliation_period(
                year=2026, month=3, is_finalized=True, finalized_at=datetime.now(UTC)
            )
        return None

    uow.reconciliation_periods.get_by_period.side_effect = fake_get_by_period
    command = UpdateTransactionCommand(transaction_id=tx.id, date=new_date)

    with pytest.raises(PeriodFinalizedError):
        await UpdateTransactionUseCase().execute(command, uow)


async def test_original_date_set_on_first_date_edit() -> None:
    uow = make_mock_uow()
    original_date = date(2026, 1, 15)
    tx = make_transaction(date=original_date)
    uow.transactions.get_by_id.return_value = tx
    new_date = date(2026, 1, 20)
    command = UpdateTransactionCommand(transaction_id=tx.id, date=new_date)

    result = await UpdateTransactionUseCase().execute(command, uow)

    assert result.transaction.date == new_date
    assert result.transaction.original_date == original_date


async def test_original_date_preserved_on_subsequent_edit() -> None:
    uow = make_mock_uow()
    first_original = date(2026, 1, 10)
    tx = make_transaction(date=date(2026, 1, 20), original_date=first_original)
    uow.transactions.get_by_id.return_value = tx
    command = UpdateTransactionCommand(transaction_id=tx.id, date=date(2026, 1, 25))

    result = await UpdateTransactionUseCase().execute(command, uow)

    assert result.transaction.original_date == first_original


async def test_original_amount_set_on_first_amount_edit() -> None:
    uow = make_mock_uow()
    original_amount = Decimal("-50.00")
    tx = make_transaction(amount=original_amount)
    uow.transactions.get_by_id.return_value = tx
    command = UpdateTransactionCommand(transaction_id=tx.id, amount=Decimal("-75.00"))

    result = await UpdateTransactionUseCase().execute(command, uow)

    assert result.transaction.amount == Decimal("-75.00")
    assert result.transaction.original_amount == original_amount


async def test_original_amount_preserved_on_subsequent_edit() -> None:
    uow = make_mock_uow()
    first_original = Decimal("-42.00")
    tx = make_transaction(amount=Decimal("-60.00"), original_amount=first_original)
    uow.transactions.get_by_id.return_value = tx
    command = UpdateTransactionCommand(transaction_id=tx.id, amount=Decimal("-99.00"))

    result = await UpdateTransactionUseCase().execute(command, uow)

    assert result.transaction.original_amount == first_original


async def test_not_found_for_missing_transaction() -> None:
    uow = make_mock_uow()
    uow.transactions.get_by_id.return_value = None
    missing_id = uuid.uuid4()
    command = UpdateTransactionCommand(transaction_id=missing_id, category="New")

    with pytest.raises(NotFoundError, match=str(missing_id)):
        await UpdateTransactionUseCase().execute(command, uow)


async def test_preserves_other_fields() -> None:
    uow = make_mock_uow()
    tx = make_transaction(
        merchant="Original Merchant",
        category="Dining Out",
        notes="Test notes",
        tags=("shared", "s50"),
        payer_percentage=50,
    )
    uow.transactions.get_by_id.return_value = tx
    command = UpdateTransactionCommand(transaction_id=tx.id, category="Fast Food")

    result = await UpdateTransactionUseCase().execute(command, uow)

    assert result.transaction.merchant == "Original Merchant"
    assert result.transaction.notes == "Test notes"
    assert result.transaction.tags == ("shared", "s50")
    assert result.transaction.payer_percentage == 50
    assert result.transaction.category == "Fast Food"


async def test_payer_percentage_update() -> None:
    uow = make_mock_uow()
    tx = make_transaction(payer_percentage=50)
    uow.transactions.get_by_id.return_value = tx
    command = UpdateTransactionCommand(transaction_id=tx.id, payer_percentage=70)

    result = await UpdateTransactionUseCase().execute(command, uow)

    assert result.transaction.payer_percentage == 70
    assert len(result.edits) == 1
    assert result.edits[0].field_name == "payer_percentage"


async def test_rejects_invalid_payer_percentage() -> None:
    uow = make_mock_uow()
    command = UpdateTransactionCommand(
        transaction_id=uuid.uuid4(), payer_percentage=150
    )

    with pytest.raises(ValidationError, match="payer_percentage"):
        await UpdateTransactionUseCase().execute(command, uow)
