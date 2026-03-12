from decimal import Decimal
import uuid

import pytest

from src.application.use_cases.export_adjustments import (
    ExportAdjustmentsCommand,
    ExportAdjustmentsUseCase,
)
from src.domain.exceptions import NotFoundError, ValidationError
from tests.fixtures.factories import make_person, make_transaction
from tests.fixtures.mocks import make_mock_uow


def _make_command(
    person_id: uuid.UUID | None = None,
    year: int = 2026,
    month: int = 1,
) -> ExportAdjustmentsCommand:
    return ExportAdjustmentsCommand(
        person_id=person_id or uuid.uuid4(), year=year, month=month
    )


async def test_happy_path_returns_csv() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice", adjustment_account="Alice Adjustments")
    bob = make_person(name="Bob", adjustment_account="Bob Adjustments")
    uow.persons.get_all.return_value = [alice, bob]

    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        )
    ]
    uow.transactions.get_shared_by_period.return_value = txs

    command = _make_command(person_id=alice.id)
    result = await ExportAdjustmentsUseCase().execute(command, uow)

    assert result.adjustment_count == 1
    assert result.person_name == "Alice"
    assert result.filename == "adjustments-alice-2026-01.csv"
    assert "Date,Amount,Merchant,Category" in result.csv_content
    assert "couplefins-adjustment" in result.csv_content


async def test_person_not_found_raises() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice", adjustment_account="Adj")
    bob = make_person(name="Bob", adjustment_account="Adj")
    uow.persons.get_all.return_value = [alice, bob]

    command = _make_command(person_id=uuid.uuid4())
    with pytest.raises(NotFoundError):
        await ExportAdjustmentsUseCase().execute(command, uow)


async def test_no_couple_raises_validation_error() -> None:
    uow = make_mock_uow()
    uow.persons.get_all.return_value = [make_person()]

    command = _make_command()
    with pytest.raises(ValidationError, match="Expected 2"):
        await ExportAdjustmentsUseCase().execute(command, uow)


async def test_empty_adjustment_account_raises() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice", adjustment_account="")
    bob = make_person(name="Bob", adjustment_account="Bob Adjustments")
    uow.persons.get_all.return_value = [alice, bob]

    command = _make_command(person_id=alice.id)
    with pytest.raises(ValidationError, match="not configured"):
        await ExportAdjustmentsUseCase().execute(command, uow)


async def test_empty_month_returns_header_only_csv() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice", adjustment_account="Adj")
    bob = make_person(name="Bob", adjustment_account="Adj")
    uow.persons.get_all.return_value = [alice, bob]
    uow.transactions.get_shared_by_period.return_value = []

    command = _make_command(person_id=alice.id)
    result = await ExportAdjustmentsUseCase().execute(command, uow)

    assert result.adjustment_count == 0
    lines = result.csv_content.strip().split("\n")
    assert len(lines) == 1  # header only


async def test_read_only_no_commit() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice", adjustment_account="Adj")
    bob = make_person(name="Bob", adjustment_account="Adj")
    uow.persons.get_all.return_value = [alice, bob]
    uow.transactions.get_shared_by_period.return_value = []

    command = _make_command(person_id=alice.id)
    await ExportAdjustmentsUseCase().execute(command, uow)

    uow.commit.assert_not_called()
