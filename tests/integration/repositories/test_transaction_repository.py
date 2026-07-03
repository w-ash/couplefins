from datetime import date
from decimal import Decimal

import attrs
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.repositories.person_repository import (
    PersonRepository,
)
from src.infrastructure.persistence.repositories.transaction_repository import (
    TransactionRepository,
)
from src.infrastructure.persistence.repositories.upload_repository import (
    UploadRepository,
)
from tests.fixtures.factories import make_person, make_transaction, make_upload


async def _seed_household_transactions(
    repo: TransactionRepository, session: AsyncSession
) -> None:
    alice = make_person(name="Alice")
    upload = make_upload(person_id=alice.id)

    await PersonRepository(session).save(alice)
    await UploadRepository(session).save(upload)

    jan_tx = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 15),
        payer_person_id=alice.id,
        payer_percentage=50,
        amount=Decimal("-100.00"),
    )
    feb_tx = make_transaction(
        upload_id=upload.id,
        date=date(2026, 2, 10),
        payer_person_id=alice.id,
        payer_percentage=50,
        amount=Decimal("-60.00"),
    )
    non_household_tx = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 20),
        payer_person_id=alice.id,
        payer_percentage=100,
        household=False,
        amount=Decimal("-30.00"),
    )

    await repo.save_batch([jan_tx, feb_tx, non_household_tx])
    await session.commit()


async def test_household_by_date_range_returns_only_household(
    db_session: AsyncSession,
) -> None:
    repo = TransactionRepository(db_session)
    await _seed_household_transactions(repo, db_session)

    result = await repo.get_household_by_date_range(date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].amount == Decimal("-100.00")
    assert result[0].household is True


async def test_household_by_date_range_excludes_out_of_range(
    db_session: AsyncSession,
) -> None:
    repo = TransactionRepository(db_session)
    await _seed_household_transactions(repo, db_session)

    result = await repo.get_household_by_date_range(date(2026, 3, 1), date(2026, 3, 31))
    assert result == []


async def test_household_by_date_range_boundary_dates(
    db_session: AsyncSession,
) -> None:
    repo = TransactionRepository(db_session)
    alice = make_person(name="Alice")
    upload = make_upload(person_id=alice.id)

    await PersonRepository(db_session).save(alice)
    await UploadRepository(db_session).save(upload)

    start_tx = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 1),
        payer_person_id=alice.id,
        payer_percentage=50,
    )
    end_tx = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 31),
        payer_person_id=alice.id,
        payer_percentage=50,
    )
    before_tx = make_transaction(
        upload_id=upload.id,
        date=date(2025, 12, 31),
        payer_person_id=alice.id,
        payer_percentage=50,
    )
    after_tx = make_transaction(
        upload_id=upload.id,
        date=date(2026, 2, 1),
        payer_person_id=alice.id,
        payer_percentage=50,
    )

    await repo.save_batch([start_tx, end_tx, before_tx, after_tx])
    await db_session.commit()

    result = await repo.get_household_by_date_range(date(2026, 1, 1), date(2026, 1, 31))
    ids = {tx.id for tx in result}
    assert start_tx.id in ids
    assert end_tx.id in ids
    assert before_tx.id not in ids
    assert after_tx.id not in ids


async def test_household_by_date_range_empty_db(db_session: AsyncSession) -> None:
    repo = TransactionRepository(db_session)
    result = await repo.get_household_by_date_range(date(2026, 1, 1), date(2026, 1, 31))
    assert result == []


async def test_get_by_person_and_original_date_range_coalesces_dates(
    db_session: AsyncSession,
) -> None:
    repo = TransactionRepository(db_session)
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    upload = make_upload(person_id=alice.id)

    persons = PersonRepository(db_session)
    await persons.save(alice)
    await persons.save(bob)
    await UploadRepository(db_session).save(upload)

    in_window = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 15),
        payer_person_id=alice.id,
        original_statement="IN WINDOW",
    )
    # Date edited out of the window in-app; original_date still inside.
    edited_out = make_transaction(
        upload_id=upload.id,
        date=date(2026, 2, 20),
        original_date=date(2026, 1, 10),
        payer_person_id=alice.id,
        original_statement="EDITED OUT",
    )
    outside = make_transaction(
        upload_id=upload.id,
        date=date(2026, 2, 5),
        payer_person_id=alice.id,
        original_statement="OUTSIDE",
    )
    other_person = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 20),
        payer_person_id=bob.id,
        original_statement="OTHER PERSON",
    )
    await repo.save_batch([in_window, edited_out, outside, other_person])
    await db_session.commit()

    result = await repo.get_by_person_and_original_date_range(
        alice.id, date(2026, 1, 1), date(2026, 1, 31)
    )
    ids = {tx.id for tx in result}
    assert ids == {in_window.id, edited_out.id}


async def _seed_flagged_transaction(repo: TransactionRepository, session: AsyncSession):
    """One saved transaction with both in-app flags set (linked + excluded)."""
    alice = make_person(name="Alice")
    upload = make_upload(person_id=alice.id)
    await PersonRepository(session).save(alice)
    await UploadRepository(session).save(upload)

    tx = make_transaction(
        upload_id=upload.id,
        payer_person_id=alice.id,
        merchant="Venmo",
        is_settlement=True,
        is_excluded=True,
    )
    await repo.save_batch([tx])
    await session.commit()
    return tx


async def test_update_mutable_fields_batch_preserves_in_app_flags(
    db_session: AsyncSession,
) -> None:
    """Accepting a re-upload "changed" row must not revert is_settlement/is_excluded."""
    repo = TransactionRepository(db_session)
    tx = await _seed_flagged_transaction(repo, db_session)

    # A freshly parsed CSV row carries default flags (False) and a new merchant.
    reparsed = attrs.evolve(
        tx, merchant="Venmo Payment", is_settlement=False, is_excluded=False
    )
    await repo.update_mutable_fields_batch([reparsed])
    await db_session.commit()

    stored = await repo.get_by_id(tx.id)
    assert stored is not None
    assert stored.merchant == "Venmo Payment"
    assert stored.is_settlement is True
    assert stored.is_excluded is True


async def test_update_mutable_fields_still_writes_in_app_flags(
    db_session: AsyncSession,
) -> None:
    """The singular update serves mark/unlink flows — it must flip the flags."""
    repo = TransactionRepository(db_session)
    tx = await _seed_flagged_transaction(repo, db_session)

    unmarked = attrs.evolve(tx, is_settlement=False, is_excluded=False)
    await repo.update_mutable_fields(unmarked)
    await db_session.commit()

    stored = await repo.get_by_id(tx.id)
    assert stored is not None
    assert stored.is_settlement is False
    assert stored.is_excluded is False
