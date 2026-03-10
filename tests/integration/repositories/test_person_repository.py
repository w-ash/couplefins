from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.repositories.person_repository import (
    PersonRepository,
)
from tests.fixtures.factories import make_person


async def test_save_and_retrieve_by_id(db_session: AsyncSession) -> None:
    repo = PersonRepository(db_session)
    person = make_person(name="Alice", adjustment_account="Adjustments")

    saved = await repo.save(person)
    await db_session.commit()

    found = await repo.get_by_id(saved.id)
    assert found is not None
    assert found.id == person.id
    assert found.name == "Alice"
    assert found.adjustment_account == "Adjustments"


async def test_save_batch_and_get_all(db_session: AsyncSession) -> None:
    repo = PersonRepository(db_session)
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")

    saved = await repo.save_batch([alice, bob])
    await db_session.commit()

    assert len(saved) == 2
    all_persons = await repo.get_all()
    assert len(all_persons) == 2
    names = {p.name for p in all_persons}
    assert names == {"Alice", "Bob"}


async def test_count_empty(db_session: AsyncSession) -> None:
    repo = PersonRepository(db_session)
    assert await repo.count() == 0


async def test_count_after_save(db_session: AsyncSession) -> None:
    repo = PersonRepository(db_session)
    await repo.save(make_person(name="Alice"))
    await db_session.commit()

    assert await repo.count() == 1


async def test_get_by_id_returns_none_for_missing(db_session: AsyncSession) -> None:
    import uuid

    repo = PersonRepository(db_session)
    assert await repo.get_by_id(uuid.uuid4()) is None


async def test_save_upserts_existing(db_session: AsyncSession) -> None:
    repo = PersonRepository(db_session)
    person = make_person(name="Alice")

    await repo.save(person)
    await db_session.commit()

    updated = make_person(id=person.id, name="Alice Updated")
    await repo.save(updated)
    await db_session.commit()

    found = await repo.get_by_id(person.id)
    assert found is not None
    assert found.name == "Alice Updated"
    assert await repo.count() == 1
