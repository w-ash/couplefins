from datetime import UTC, datetime
import uuid

import pytest

from src.application.use_cases._shared.transaction_pipeline import (
    compute_edit,
    fetch_and_validate,
    validate_payer_percentage,
)
from src.domain.exceptions import NotFoundError, PeriodFinalizedError, ValidationError
from tests.fixtures.factories import make_reconciliation_period, make_transaction
from tests.fixtures.mocks import make_mock_uow


async def test_fetch_and_validate_returns_transactions_by_id() -> None:
    uow = make_mock_uow()
    tx1 = make_transaction()
    tx2 = make_transaction()
    uow.transactions.get_by_ids.return_value = [tx1, tx2]

    result = await fetch_and_validate(uow, [tx1.id, tx2.id])

    assert result == {tx1.id: tx1, tx2.id: tx2}


async def test_fetch_and_validate_raises_not_found() -> None:
    uow = make_mock_uow()
    uow.transactions.get_by_ids.return_value = []
    missing_id = uuid.uuid4()

    with pytest.raises(NotFoundError, match=str(missing_id)):
        await fetch_and_validate(uow, [missing_id])


async def test_fetch_and_validate_checks_finalization() -> None:
    uow = make_mock_uow()
    tx = make_transaction()
    uow.transactions.get_by_ids.return_value = [tx]
    uow.reconciliation_periods.get_by_period.return_value = make_reconciliation_period(
        year=tx.date.year,
        month=tx.date.month,
        is_finalized=True,
        finalized_at=datetime.now(UTC),
    )

    with pytest.raises(PeriodFinalizedError):
        await fetch_and_validate(uow, [tx.id])


def test_compute_edit_returns_edit_when_changed() -> None:
    tx = make_transaction(category="Dining Out")
    now = datetime.now(UTC)

    edit = compute_edit(tx, "category", "Dining Out", "Fast Food", now)

    assert edit is not None
    assert edit.field_name == "category"
    assert edit.old_value == "Dining Out"
    assert edit.new_value == "Fast Food"
    assert edit.transaction_id == tx.id
    assert edit.edited_at == now


def test_compute_edit_returns_none_when_unchanged() -> None:
    tx = make_transaction(category="Dining Out")

    edit = compute_edit(tx, "category", "Dining Out", "Dining Out")

    assert edit is None


def test_compute_edit_handles_none_values() -> None:
    tx = make_transaction(payer_percentage=None)

    edit = compute_edit(tx, "payer_percentage", None, 50)

    assert edit is not None
    assert not edit.old_value
    assert edit.new_value == "50"


def test_validate_payer_percentage_accepts_valid() -> None:
    validate_payer_percentage(0)
    validate_payer_percentage(50)
    validate_payer_percentage(100)


def test_validate_payer_percentage_rejects_too_high() -> None:
    with pytest.raises(ValidationError, match="payer_percentage"):
        validate_payer_percentage(150)


def test_validate_payer_percentage_rejects_negative() -> None:
    with pytest.raises(ValidationError, match="payer_percentage"):
        validate_payer_percentage(-1)
