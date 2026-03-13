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
