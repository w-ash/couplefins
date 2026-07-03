import uuid

import pytest

from src.application.use_cases.preview_csv import PreviewCsvCommand, PreviewCsvUseCase
from src.domain.entities.category import Category
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import (
    make_category,
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
) -> PreviewCsvCommand:
    return PreviewCsvCommand(
        csv_text=csv_text,
        person_id=person_id or uuid.uuid4(),
    )


async def test_all_new_transactions() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = [
        make_category(name="Groceries"),
        make_category(name="Gas"),
        make_category(name="Dining Out"),
    ]
    uow.transactions.get_by_person_and_original_date_range.return_value = []
    command = _make_command(person_id=person.id)

    result = await PreviewCsvUseCase().execute(command, uow)

    assert len(result.new_transactions) == 3
    assert result.unchanged_count == 0
    assert result.changed_transactions == []
    assert result.unmapped_categories == []
    assert result.new_transactions[0].merchant == "Grocery Store"
    assert result.new_transactions[0].household is True
    assert result.new_transactions[0].payer_percentage == 50
    assert result.new_transactions[2].payer_percentage == 70


async def test_detects_unchanged_transactions() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = []
    # Simulate existing transaction matching by natural key
    existing = make_transaction(
        payer_person_id=person.id,
        original_statement="GROCERY STORE",
        account="Chase",
        merchant="Grocery Store",
        category="Groceries",
        tags=("shared",),
        payer_percentage=50,
    )
    uow.transactions.get_by_person_and_original_date_range.return_value = [existing]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        f'{existing.date.isoformat()},Grocery Store,Groceries,Chase,GROCERY STORE,,"{existing.amount}",shared\n'
    )
    command = _make_command(csv_text=csv, person_id=person.id)

    result = await PreviewCsvUseCase().execute(command, uow)

    assert result.new_transactions == []
    assert result.unchanged_count == 1
    assert result.changed_transactions == []


async def test_detects_changed_transactions() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = []
    existing = make_transaction(
        payer_person_id=person.id,
        original_statement="GROCERY STORE",
        account="Chase",
        merchant="Old Name",
        category="Groceries",
        tags=("shared",),
        payer_percentage=50,
    )
    uow.transactions.get_by_person_and_original_date_range.return_value = [existing]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        f'{existing.date.isoformat()},New Name,Groceries,Chase,GROCERY STORE,,"{existing.amount}",shared\n'
    )
    command = _make_command(csv_text=csv, person_id=person.id)

    result = await PreviewCsvUseCase().execute(command, uow)

    assert result.new_transactions == []
    assert result.unchanged_count == 0
    assert len(result.changed_transactions) == 1
    ct = result.changed_transactions[0]
    assert ct.existing_id == existing.id
    assert ct.incoming.merchant == "New Name"
    assert ct.existing.merchant == "Old Name"
    assert any(d.field_name == "merchant" for d in ct.diffs)


async def test_reports_new_and_unmapped_categories_without_creating() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.categories.get_all.return_value = [
        make_category(name="Groceries"),
    ]
    uow.transactions.get_by_person_and_original_date_range.return_value = []
    command = _make_command()

    result = await PreviewCsvUseCase().execute(command, uow)

    # Both "Dining Out" and "Gas" are unknown → reported as unmapped
    assert result.unmapped_categories == ["Dining Out", "Gas"]


async def test_reports_existing_unmapped_categories() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.categories.get_all.return_value = [
        make_category(name="Groceries"),
        Category(id=uuid.uuid4(), name="Gas", group_id=None),
    ]
    uow.transactions.get_by_person_and_original_date_range.return_value = []
    command = _make_command()

    result = await PreviewCsvUseCase().execute(command, uow)

    # "Dining Out" is new, "Gas" is unmapped in DB → both reported
    assert result.unmapped_categories == ["Dining Out", "Gas"]


async def test_reports_removed_transactions() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = []
    kept = make_transaction(
        payer_person_id=person.id,
        original_statement="GROCERY STORE",
        account="Chase",
        merchant="Grocery Store",
        category="Groceries",
        tags=("shared",),
        payer_percentage=50,
        notes="",
    )
    dropped = make_transaction(
        payer_person_id=person.id,
        original_statement="COFFEE SHOP",
        account="Chase",
        merchant="Coffee Shop",
        date=kept.date,
    )
    uow.transactions.get_by_person_and_original_date_range.return_value = [
        kept,
        dropped,
    ]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        f'{kept.date.isoformat()},Grocery Store,Groceries,Chase,GROCERY STORE,,"{kept.amount}",shared\n'
    )
    command = _make_command(csv_text=csv, person_id=person.id)

    result = await PreviewCsvUseCase().execute(command, uow)

    assert result.unchanged_count == 1
    assert len(result.removed_transactions) == 1
    assert result.removed_transactions[0].merchant == "Coffee Shop"


async def test_raises_not_found_for_missing_person() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = None
    command = _make_command()

    with pytest.raises(NotFoundError, match="Person"):
        await PreviewCsvUseCase().execute(command, uow)


async def test_handles_empty_csv() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.categories.get_all.return_value = []
    csv_text = "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    command = _make_command(csv_text=csv_text)

    result = await PreviewCsvUseCase().execute(command, uow)

    assert result.new_transactions == []
    assert result.unchanged_count == 0
    assert result.changed_transactions == []


async def test_never_persists_data() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.categories.get_all.return_value = []
    uow.transactions.get_by_person_and_original_date_range.return_value = []
    command = _make_command()

    await PreviewCsvUseCase().execute(command, uow)

    uow.uploads.save.assert_not_called()
    uow.transactions.save_batch.assert_not_called()
    uow.transactions.delete_by_ids.assert_not_called()
    uow.transaction_edits.delete_by_transaction_ids.assert_not_called()
    uow.settlement_transaction_links.delete_by_transaction_ids.assert_not_called()
    uow.categories.save_batch.assert_not_called()
    uow.commit.assert_not_called()
