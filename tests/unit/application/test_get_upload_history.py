from datetime import UTC, date, datetime

from src.application.use_cases.get_upload_history import (
    GetUploadHistoryCommand,
    GetUploadHistoryUseCase,
)
from tests.fixtures.factories import make_person
from tests.fixtures.mocks import make_mock_uow


async def test_enriches_with_person_names() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    uow.persons.get_all.return_value = [alice, bob]

    from src.domain.entities.upload import UploadWithCounts

    uow.uploads.get_all_with_transaction_counts.return_value = [
        UploadWithCounts(
            id=alice.id,
            person_id=alice.id,
            filename="alice-jan.csv",
            uploaded_at=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
            transaction_count=47,
            household_count=23,
            date_range_start=date(2026, 1, 1),
            date_range_end=date(2026, 1, 31),
        ),
        UploadWithCounts(
            id=bob.id,
            person_id=bob.id,
            filename="bob-jan.csv",
            uploaded_at=datetime(2026, 1, 14, 9, 0, tzinfo=UTC),
            transaction_count=38,
            household_count=19,
            date_range_start=date(2026, 1, 1),
            date_range_end=date(2026, 1, 28),
        ),
    ]

    result = await GetUploadHistoryUseCase().execute(GetUploadHistoryCommand(), uow)

    assert len(result.entries) == 2
    assert result.entries[0].person_name == "Alice"
    assert result.entries[0].transaction_count == 47
    assert result.entries[0].household_count == 23
    assert result.entries[1].person_name == "Bob"
    assert result.entries[1].filename == "bob-jan.csv"


async def test_empty_result() -> None:
    uow = make_mock_uow()
    uow.persons.get_all.return_value = []
    uow.uploads.get_all_with_transaction_counts.return_value = []

    result = await GetUploadHistoryUseCase().execute(GetUploadHistoryCommand(), uow)

    assert result.entries == []
