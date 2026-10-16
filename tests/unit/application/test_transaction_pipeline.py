from datetime import UTC, datetime
import uuid

import pytest

from src.application.use_cases._shared.command_validators import as_validation_error
from src.application.use_cases._shared.transaction_pipeline import (
    NO_PAYER_SPLIT,
    compute_edit,
    fetch_and_validate,
    reject_joint_rows,
)
from src.domain.exceptions import NotFoundError, PeriodFinalizedError, ValidationError
from src.domain.split_rules import check_payer_percentage
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
    uow.reconciliation_periods.get_by_periods.return_value = [
        make_reconciliation_period(
            year=tx.date.year,
            month=tx.date.month,
            is_finalized=True,
            finalized_at=datetime.now(UTC),
        )
    ]

    with pytest.raises(PeriodFinalizedError):
        await fetch_and_validate(uow, [tx.id])


def test_compute_edit_returns_edit_when_changed() -> None:
    tx = make_transaction(category="Dining Out")
    now = datetime.now(UTC)

    edit = compute_edit(tx, "category", "Dining Out", "Fast Food", now=now)

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


def test_compute_edit_handles_default_payer_percentage() -> None:
    tx = make_transaction(payer_percentage=100)

    edit = compute_edit(tx, "payer_percentage", 100, 50)

    assert edit is not None
    assert edit.old_value == "100"
    assert edit.new_value == "50"


def test_as_validation_error_passes_a_valid_value() -> None:
    as_validation_error(check_payer_percentage, 0)
    as_validation_error(check_payer_percentage, 50)
    as_validation_error(check_payer_percentage, 100)


@pytest.mark.parametrize("pct", [150, -1])
def test_as_validation_error_raises_the_checks_value_error(pct: int) -> None:
    with pytest.raises(ValidationError, match="payer_percentage"):
        as_validation_error(check_payer_percentage, pct)


def test_reject_joint_rows_names_the_reason() -> None:
    rows = [make_transaction(), make_transaction(joint=True)]

    with pytest.raises(ValidationError, match="no payer split"):
        reject_joint_rows(rows, NO_PAYER_SPLIT)


def test_reject_joint_rows_passes_personal_rows() -> None:
    reject_joint_rows([make_transaction(), make_transaction()], NO_PAYER_SPLIT)


def test_compute_edit_passes_through_edited_by_person_id() -> None:
    tx = make_transaction(category="Dining Out")
    person_id = uuid.uuid4()

    edit = compute_edit(
        tx, "category", "Dining Out", "Fast Food", edited_by_person_id=person_id
    )

    assert edit is not None
    assert edit.edited_by_person_id == person_id


def test_compute_edit_defaults_edited_by_person_id_to_none() -> None:
    tx = make_transaction(category="Dining Out")

    edit = compute_edit(tx, "category", "Dining Out", "Fast Food")

    assert edit is not None
    assert edit.edited_by_person_id is None
