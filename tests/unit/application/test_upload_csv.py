from decimal import Decimal
import uuid

import pytest

from src.application.use_cases.upload_csv import UploadCsvCommand, UploadCsvUseCase
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import (
    make_category_mapping,
    make_person,
    make_transaction,
)
from tests.fixtures.mocks import make_mock_uow

VALID_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-50.00",shared\n'
    '2026-01-16,Gas Station,Gas,Chase,GAS STATION,,"-30.00",\n'
    '2026-01-17,Restaurant,Dining Out,Chase,RESTAURANT,,"-80.00","shared,s70"\n'
)


def _make_command(
    csv_text: str = VALID_CSV,
    person_id: uuid.UUID | None = None,
    accepted_change_ids: frozenset[uuid.UUID] = frozenset(),
) -> UploadCsvCommand:
    return UploadCsvCommand(
        csv_text=csv_text,
        person_id=person_id or uuid.uuid4(),
        filename="test.csv",
        accepted_change_ids=accepted_change_ids,
    )


async def test_uploads_all_new_transactions() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.category_mappings.get_all.return_value = [
        make_category_mapping(category="Groceries"),
        make_category_mapping(category="Gas"),
        make_category_mapping(category="Dining Out"),
    ]
    uow.transactions.get_by_person_and_date_range.return_value = []
    command = _make_command(person_id=person.id)

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.new_count == 3
    assert result.updated_count == 0
    assert result.skipped_count == 0
    assert result.unmapped_categories == []
    uow.uploads.save.assert_called_once()
    uow.transactions.save_batch.assert_called_once()
    uow.commit.assert_called_once()
    # No new categories to auto-create
    uow.category_mappings.save_batch.assert_not_called()


async def test_skips_unchanged_transactions() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.category_mappings.get_all.return_value = []
    existing = make_transaction(
        payer_person_id=person.id,
        original_statement="GROCERY STORE",
        account="Chase",
        merchant="Grocery Store",
        category="Groceries",
        amount=Decimal("-50.00"),
        tags=("shared",),
        payer_percentage=50,
        notes="",
    )
    uow.transactions.get_by_person_and_date_range.return_value = [existing]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        f'{existing.date.isoformat()},Grocery Store,Groceries,Chase,GROCERY STORE,,"{existing.amount}",shared\n'
    )
    command = _make_command(csv_text=csv, person_id=person.id)

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.new_count == 0
    assert result.updated_count == 0
    assert result.skipped_count == 1
    uow.transactions.save_batch.assert_not_called()


async def test_updates_accepted_changes() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.category_mappings.get_all.return_value = []
    existing = make_transaction(
        payer_person_id=person.id,
        original_statement="GROCERY STORE",
        account="Chase",
        merchant="Old Name",
        category="Groceries",
        amount=Decimal("-50.00"),
        tags=("shared",),
        payer_percentage=50,
        notes="",
    )
    uow.transactions.get_by_person_and_date_range.return_value = [existing]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        f'{existing.date.isoformat()},New Name,Groceries,Chase,GROCERY STORE,,"{existing.amount}",shared\n'
    )
    command = _make_command(
        csv_text=csv,
        person_id=person.id,
        accepted_change_ids=frozenset({existing.id}),
    )

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.new_count == 0
    assert result.updated_count == 1
    assert result.skipped_count == 0
    uow.transactions.update_mutable_fields.assert_called_once()


async def test_skips_rejected_changes() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.category_mappings.get_all.return_value = []
    existing = make_transaction(
        payer_person_id=person.id,
        original_statement="GROCERY STORE",
        account="Chase",
        merchant="Old Name",
        category="Groceries",
        amount=Decimal("-50.00"),
        tags=("shared",),
        payer_percentage=50,
        notes="",
    )
    uow.transactions.get_by_person_and_date_range.return_value = [existing]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        f'{existing.date.isoformat()},New Name,Groceries,Chase,GROCERY STORE,,"{existing.amount}",shared\n'
    )
    # No accepted_change_ids → reject the change
    command = _make_command(csv_text=csv, person_id=person.id)

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.new_count == 0
    assert result.updated_count == 0
    assert result.skipped_count == 1
    uow.transactions.update_mutable_fields.assert_not_called()


async def test_auto_creates_unmapped_categories_on_upload() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.category_mappings.get_all.return_value = [
        make_category_mapping(category="Groceries"),
    ]
    uow.transactions.get_by_person_and_date_range.return_value = []
    command = _make_command()

    result = await UploadCsvUseCase().execute(command, uow)

    # "Dining Out" and "Gas" are new → auto-created with group_id=None
    uow.category_mappings.save_batch.assert_called_once()
    saved = uow.category_mappings.save_batch.call_args[0][0]
    saved_cats = sorted(m.category for m in saved)
    assert saved_cats == ["Dining Out", "Gas"]
    assert all(m.group_id is None for m in saved)
    # They should be reported as unmapped
    assert result.unmapped_categories == ["Dining Out", "Gas"]


async def test_reports_existing_unmapped_categories() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.category_mappings.get_all.return_value = [
        make_category_mapping(category="Groceries"),
        make_category_mapping(category="Gas", group_id=None),
        make_category_mapping(category="Dining Out", group_id=None),
    ]
    uow.transactions.get_by_person_and_date_range.return_value = []
    command = _make_command()

    result = await UploadCsvUseCase().execute(command, uow)

    # No new categories to create
    uow.category_mappings.save_batch.assert_not_called()
    # But existing unmapped ones are reported
    assert result.unmapped_categories == ["Dining Out", "Gas"]


async def test_raises_not_found_for_missing_person() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = None
    command = _make_command()

    with pytest.raises(NotFoundError, match="Person"):
        await UploadCsvUseCase().execute(command, uow)


async def test_handles_empty_csv() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.category_mappings.get_all.return_value = []
    csv_text = "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    command = _make_command(csv_text=csv_text)

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.new_count == 0
    assert result.updated_count == 0
    assert result.skipped_count == 0
    uow.transactions.save_batch.assert_not_called()
