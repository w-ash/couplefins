from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.repositories.transaction_repository import (
    TransactionRepository,
)
from src.infrastructure.persistence.repositories.upload_repository import (
    UploadRepository,
)
from tests.fixtures.factories import make_person, make_transaction, make_upload


async def test_uploads_with_transactions_in_range(db_session: AsyncSession) -> None:
    tx_repo = TransactionRepository(db_session)
    up_repo = UploadRepository(db_session)

    alice = make_person(name="Alice")
    jan_upload = make_upload(person_id=alice.id, filename="jan.csv")
    feb_upload = make_upload(person_id=alice.id, filename="feb.csv")

    await up_repo.save_batch([jan_upload, feb_upload])

    jan_tx = make_transaction(
        upload_id=jan_upload.id,
        date=date(2026, 1, 15),
        payer_person_id=alice.id,
        amount=Decimal("-50.00"),
    )
    feb_tx = make_transaction(
        upload_id=feb_upload.id,
        date=date(2026, 2, 10),
        payer_person_id=alice.id,
        amount=Decimal("-30.00"),
    )
    await tx_repo.save_batch([jan_tx, feb_tx])
    await db_session.commit()

    result = await up_repo.get_by_person_ids_with_transactions_in_date_range(
        [alice.id], date(2026, 1, 1), date(2026, 1, 31)
    )
    assert len(result) == 1
    assert result[0].id == jan_upload.id


async def test_excludes_out_of_range(db_session: AsyncSession) -> None:
    tx_repo = TransactionRepository(db_session)
    up_repo = UploadRepository(db_session)

    alice = make_person(name="Alice")
    upload = make_upload(person_id=alice.id)
    await up_repo.save(upload)

    tx = make_transaction(
        upload_id=upload.id,
        date=date(2026, 3, 15),
        payer_person_id=alice.id,
    )
    await tx_repo.save(tx)
    await db_session.commit()

    result = await up_repo.get_by_person_ids_with_transactions_in_date_range(
        [alice.id], date(2026, 1, 1), date(2026, 1, 31)
    )
    assert result == []


async def test_excludes_other_persons(db_session: AsyncSession) -> None:
    tx_repo = TransactionRepository(db_session)
    up_repo = UploadRepository(db_session)

    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    bob_upload = make_upload(person_id=bob.id)
    await up_repo.save(bob_upload)

    tx = make_transaction(
        upload_id=bob_upload.id,
        date=date(2026, 1, 15),
        payer_person_id=bob.id,
    )
    await tx_repo.save(tx)
    await db_session.commit()

    result = await up_repo.get_by_person_ids_with_transactions_in_date_range(
        [alice.id], date(2026, 1, 1), date(2026, 1, 31)
    )
    assert result == []


async def test_empty_person_ids(db_session: AsyncSession) -> None:
    up_repo = UploadRepository(db_session)
    result = await up_repo.get_by_person_ids_with_transactions_in_date_range(
        [], date(2026, 1, 1), date(2026, 1, 31)
    )
    assert result == []


async def test_get_all_with_transaction_counts(db_session: AsyncSession) -> None:
    tx_repo = TransactionRepository(db_session)
    up_repo = UploadRepository(db_session)

    alice = make_person(name="Alice")
    bob = make_person(name="Bob")

    alice_upload = make_upload(person_id=alice.id, filename="alice-jan.csv")
    bob_upload = make_upload(person_id=bob.id, filename="bob-jan.csv")
    await up_repo.save_batch([alice_upload, bob_upload])

    tx1 = make_transaction(
        upload_id=alice_upload.id,
        date=date(2026, 1, 10),
        payer_person_id=alice.id,
        amount=Decimal("-50.00"),
        tags=("shared",),
    )
    tx2 = make_transaction(
        upload_id=alice_upload.id,
        date=date(2026, 1, 20),
        payer_person_id=alice.id,
        amount=Decimal("-30.00"),
        tags=(),
        payer_percentage=None,
    )
    tx3 = make_transaction(
        upload_id=bob_upload.id,
        date=date(2026, 1, 15),
        payer_person_id=bob.id,
        amount=Decimal("-100.00"),
        tags=("shared",),
    )
    await tx_repo.save_batch([tx1, tx2, tx3])
    await db_session.commit()

    result = await up_repo.get_all_with_transaction_counts()

    assert len(result) == 2
    # Both uploads returned with correct counts
    by_filename = {r.filename: r for r in result}
    alice_row = by_filename["alice-jan.csv"]
    assert alice_row.transaction_count == 2
    assert alice_row.shared_count == 1
    assert alice_row.date_range_start == date(2026, 1, 10)
    assert alice_row.date_range_end == date(2026, 1, 20)

    bob_row = by_filename["bob-jan.csv"]
    assert bob_row.transaction_count == 1
    assert bob_row.shared_count == 1
    assert bob_row.date_range_start == date(2026, 1, 15)
    assert bob_row.date_range_end == date(2026, 1, 15)


async def test_get_all_with_transaction_counts_empty_upload(
    db_session: AsyncSession,
) -> None:
    up_repo = UploadRepository(db_session)
    upload = make_upload(filename="empty.csv")
    await up_repo.save(upload)
    await db_session.commit()

    result = await up_repo.get_all_with_transaction_counts()

    assert len(result) == 1
    assert result[0].transaction_count == 0
    assert result[0].shared_count == 0
    assert result[0].date_range_start is None
    assert result[0].date_range_end is None


async def test_no_duplicate_uploads(db_session: AsyncSession) -> None:
    tx_repo = TransactionRepository(db_session)
    up_repo = UploadRepository(db_session)

    alice = make_person(name="Alice")
    upload = make_upload(person_id=alice.id)
    await up_repo.save(upload)

    tx1 = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 10),
        payer_person_id=alice.id,
        merchant="Store A",
    )
    tx2 = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 20),
        payer_person_id=alice.id,
        merchant="Store B",
    )
    await tx_repo.save_batch([tx1, tx2])
    await db_session.commit()

    result = await up_repo.get_by_person_ids_with_transactions_in_date_range(
        [alice.id], date(2026, 1, 1), date(2026, 1, 31)
    )
    assert len(result) == 1
    assert result[0].id == upload.id
