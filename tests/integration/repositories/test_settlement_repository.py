from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.repositories.person_repository import (
    PersonRepository,
)
from src.infrastructure.persistence.repositories.settlement_repository import (
    SettlementRepository,
)
from tests.fixtures.factories import make_person, make_settlement


async def test_get_all_returns_settlements_across_periods(
    db_session: AsyncSession,
) -> None:
    """The all-time ledger fetch returns every settlement regardless of its
    year/month annotation. Ordering is not guaranteed — the ledger sorts
    payments chronologically itself."""
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    persons = PersonRepository(db_session)
    await persons.save(alice)
    await persons.save(bob)

    repo = SettlementRepository(db_session)
    jan = make_settlement(
        year=2026,
        month=1,
        amount=Decimal("50.00"),
        from_person_id=alice.id,
        to_person_id=bob.id,
        settled_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    prev_year = make_settlement(
        year=2025,
        month=11,
        amount=Decimal("30.00"),
        from_person_id=bob.id,
        to_person_id=alice.id,
        settled_at=datetime(2025, 12, 1, tzinfo=UTC),
    )
    await repo.save(jan)
    await repo.save(prev_year)
    await db_session.commit()

    result = await repo.get_all()

    assert {s.id for s in result} == {jan.id, prev_year.id}


async def test_get_all_empty_db(db_session: AsyncSession) -> None:
    repo = SettlementRepository(db_session)
    assert await repo.get_all() == []
