import uuid

import pytest

from src.application.use_cases.upload_csv import UploadCsvCommand, UploadCsvUseCase
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import make_category_mapping, make_person
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
) -> UploadCsvCommand:
    return UploadCsvCommand(
        csv_text=csv_text,
        person_id=person_id or uuid.uuid4(),
        filename="test.csv",
        year=2026,
        month=1,
    )


async def test_uploads_all_transactions() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.category_mappings.get_all.return_value = [
        make_category_mapping(category="Groceries"),
        make_category_mapping(category="Gas"),
        make_category_mapping(category="Dining Out"),
    ]
    command = _make_command(person_id=person.id)

    result = await UploadCsvUseCase(uow).execute(command)

    assert result.total_transactions == 3
    assert result.shared_count == 2
    assert result.personal_count == 1
    assert result.unmapped_categories == []
    uow.uploads.save.assert_called_once()
    uow.transactions.save_batch.assert_called_once()
    uow.commit.assert_called_once()


async def test_detects_unmapped_categories() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.category_mappings.get_all.return_value = [
        make_category_mapping(category="Groceries"),
    ]
    command = _make_command()

    result = await UploadCsvUseCase(uow).execute(command)

    assert result.unmapped_categories == ["Dining Out", "Gas"]


async def test_raises_not_found_for_missing_person() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = None
    command = _make_command()

    with pytest.raises(NotFoundError, match="Person"):
        await UploadCsvUseCase(uow).execute(command)


async def test_handles_empty_csv() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.category_mappings.get_all.return_value = []
    csv_text = "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    command = _make_command(csv_text=csv_text)

    result = await UploadCsvUseCase(uow).execute(command)

    assert result.total_transactions == 0
    assert result.shared_count == 0
    assert result.personal_count == 0
    uow.transactions.save_batch.assert_not_called()
