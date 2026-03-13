from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.repositories.transaction_repository import (
    TransactionRepository,
)
from tests.fixtures.factories import make_person, make_transaction, make_upload


async def _seed_shared_transactions(
    repo: TransactionRepository, session: AsyncSession
) -> None:
    alice = make_person(name="Alice")
    upload = make_upload(person_id=alice.id)

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
    non_shared_tx = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 20),
        payer_person_id=alice.id,
        payer_percentage=None,
        amount=Decimal("-30.00"),
    )

    await repo.save_batch([jan_tx, feb_tx, non_shared_tx])
    await session.commit()


async def test_shared_by_date_range_returns_only_shared(
    db_session: AsyncSession,
) -> None:
    repo = TransactionRepository(db_session)
    await _seed_shared_transactions(repo, db_session)

    result = await repo.get_shared_by_date_range(date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].amount == Decimal("-100.00")
    assert result[0].is_shared is True


async def test_shared_by_date_range_excludes_out_of_range(
    db_session: AsyncSession,
) -> None:
    repo = TransactionRepository(db_session)
    await _seed_shared_transactions(repo, db_session)

    result = await repo.get_shared_by_date_range(date(2026, 3, 1), date(2026, 3, 31))
    assert result == []


async def test_shared_by_date_range_boundary_dates(
    db_session: AsyncSession,
) -> None:
    repo = TransactionRepository(db_session)
    alice = make_person(name="Alice")
    upload = make_upload(person_id=alice.id)

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

    result = await repo.get_shared_by_date_range(date(2026, 1, 1), date(2026, 1, 31))
    ids = {tx.id for tx in result}
    assert start_tx.id in ids
    assert end_tx.id in ids
    assert before_tx.id not in ids
    assert after_tx.id not in ids


async def test_shared_by_date_range_empty_db(db_session: AsyncSession) -> None:
    repo = TransactionRepository(db_session)
    result = await repo.get_shared_by_date_range(date(2026, 1, 1), date(2026, 1, 31))
    assert result == []
