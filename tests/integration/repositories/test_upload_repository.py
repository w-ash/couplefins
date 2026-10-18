from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.upload import MANUAL_IMPORTER
from src.infrastructure.persistence.repositories.account_repository import (
    AccountRepository,
)
from src.infrastructure.persistence.repositories.person_repository import (
    PersonRepository,
)
from src.infrastructure.persistence.repositories.transaction_repository import (
    TransactionRepository,
)
from src.infrastructure.persistence.repositories.upload_repository import (
    UploadRepository,
)
from tests.fixtures.factories import (
    make_joint_account,
    make_person,
    make_transaction,
    make_upload,
)
from tests.integration.seed import save_transactions


async def test_uploads_with_transactions_in_range(db_session: AsyncSession) -> None:
    person_repo = PersonRepository(db_session)
    up_repo = UploadRepository(db_session)

    alice = make_person(name="Alice")
    await person_repo.save(alice)

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
    await save_transactions(db_session, [jan_tx, feb_tx])
    await db_session.commit()

    result = await up_repo.get_by_person_ids_with_transactions_in_date_range(
        [alice.id], date(2026, 1, 1), date(2026, 1, 31)
    )
    assert len(result) == 1
    assert result[0].id == jan_upload.id


async def test_excludes_out_of_range(db_session: AsyncSession) -> None:
    person_repo = PersonRepository(db_session)
    up_repo = UploadRepository(db_session)

    alice = make_person(name="Alice")
    await person_repo.save(alice)

    upload = make_upload(person_id=alice.id)
    await up_repo.save(upload)

    tx = make_transaction(
        upload_id=upload.id,
        date=date(2026, 3, 15),
        payer_person_id=alice.id,
    )
    await save_transactions(db_session, [tx])
    await db_session.commit()

    result = await up_repo.get_by_person_ids_with_transactions_in_date_range(
        [alice.id], date(2026, 1, 1), date(2026, 1, 31)
    )
    assert result == []


async def test_excludes_other_persons(db_session: AsyncSession) -> None:
    person_repo = PersonRepository(db_session)
    up_repo = UploadRepository(db_session)

    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    await person_repo.save_batch([alice, bob])

    bob_upload = make_upload(person_id=bob.id)
    await up_repo.save(bob_upload)

    tx = make_transaction(
        upload_id=bob_upload.id,
        date=date(2026, 1, 15),
        payer_person_id=bob.id,
    )
    await save_transactions(db_session, [tx])
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
    person_repo = PersonRepository(db_session)
    up_repo = UploadRepository(db_session)

    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    await person_repo.save_batch([alice, bob])

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
        payer_percentage=100,
        household=False,
    )
    tx3 = make_transaction(
        upload_id=bob_upload.id,
        date=date(2026, 1, 15),
        payer_person_id=bob.id,
        amount=Decimal("-100.00"),
        tags=("shared",),
    )
    await save_transactions(db_session, [tx1, tx2, tx3])
    await db_session.commit()

    result = await up_repo.get_all_with_transaction_counts()

    assert len(result) == 2
    by_filename = {r.filename: r for r in result}
    alice_row = by_filename["alice-jan.csv"]
    assert alice_row.transaction_count == 2
    assert alice_row.household_count == 1
    assert alice_row.date_range_start == date(2026, 1, 10)
    assert alice_row.date_range_end == date(2026, 1, 20)

    bob_row = by_filename["bob-jan.csv"]
    assert bob_row.transaction_count == 1
    assert bob_row.household_count == 1
    assert bob_row.date_range_start == date(2026, 1, 15)
    assert bob_row.date_range_end == date(2026, 1, 15)


async def test_get_all_with_transaction_counts_empty_upload(
    db_session: AsyncSession,
) -> None:
    person_repo = PersonRepository(db_session)
    up_repo = UploadRepository(db_session)

    person = make_person(name="Test")
    await person_repo.save(person)

    upload = make_upload(person_id=person.id, filename="empty.csv")
    await up_repo.save(upload)
    await db_session.commit()

    result = await up_repo.get_all_with_transaction_counts()

    assert len(result) == 1
    assert result[0].transaction_count == 0
    assert result[0].household_count == 0
    assert result[0].date_range_start is None
    assert result[0].date_range_end is None


async def test_no_duplicate_uploads(db_session: AsyncSession) -> None:
    person_repo = PersonRepository(db_session)
    up_repo = UploadRepository(db_session)

    alice = make_person(name="Alice")
    await person_repo.save(alice)

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
    await save_transactions(db_session, [tx1, tx2])
    await db_session.commit()

    result = await up_repo.get_by_person_ids_with_transactions_in_date_range(
        [alice.id], date(2026, 1, 1), date(2026, 1, 31)
    )
    assert len(result) == 1
    assert result[0].id == upload.id


async def test_manual_uploads_are_neither_history_nor_an_import(
    db_session: AsyncSession,
) -> None:
    """US-HOUSE-11: a manual upload holds hand-entered rows; it is left out
    of Upload history and never counts as the person's upload for a month."""
    person_repo = PersonRepository(db_session)
    up_repo = UploadRepository(db_session)
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    await person_repo.save_batch([alice, bob])
    imported = make_upload(person_id=alice.id, filename="alice-jan.csv")
    manual = make_upload(person_id=bob.id, importer=MANUAL_IMPORTER)
    await up_repo.save_batch([imported, manual])
    await save_transactions(
        db_session,
        [make_transaction(upload_id=imported.id, payer_person_id=alice.id)],
    )
    await AccountRepository(db_session).add_missing([make_joint_account("Escrow")])
    await TransactionRepository(db_session).save_batch([
        make_transaction(
            upload_id=manual.id, joint=True, account="Escrow", is_excluded=True
        )
    ])
    await db_session.commit()

    history = await up_repo.get_all_with_transaction_counts()
    in_range = await up_repo.get_by_person_ids_with_transactions_in_date_range(
        [alice.id, bob.id], date(2026, 1, 1), date(2026, 1, 31)
    )
    in_period = await up_repo.get_by_person_ids_with_transactions_in_period(
        [alice.id, bob.id], 2026, 1
    )

    assert [u.id for u in history] == [imported.id]
    assert [u.id for u in in_range] == [imported.id]
    assert [u.id for u in in_period] == [imported.id]
