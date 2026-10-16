from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.repositories.account_repository import (
    AccountRepository,
)
from src.infrastructure.persistence.repositories.person_repository import (
    PersonRepository,
)
from tests.fixtures.factories import make_account, make_joint_account, make_person


async def test_add_missing_inserts_new_accounts_and_skips_existing(
    db_session: AsyncSession,
) -> None:
    alice = make_person(name="Alice")
    await PersonRepository(db_session).save(alice)
    chase = make_account(name="Chase", owner_person_id=alice.id)
    joint = make_account(name="House", kind="joint")
    repo = AccountRepository(db_session)
    await repo.add_missing([chase])
    await db_session.commit()

    await repo.add_missing([chase, joint])
    await db_session.commit()

    assert sorted(await repo.get_all(), key=lambda a: a.name) == [chase, joint]


async def test_get_by_ids_and_delete_by_ids(db_session: AsyncSession) -> None:
    alice = make_person(name="Alice")
    await PersonRepository(db_session).save(alice)
    chase = make_account(name="Chase", owner_person_id=alice.id)
    amex = make_account(name="Amex", owner_person_id=alice.id)
    joint = make_joint_account("Joint Checking")
    repo = AccountRepository(db_session)
    await repo.add_missing([chase, amex, joint])
    await db_session.commit()

    found = await repo.get_by_ids([chase.id, joint.id])
    assert sorted(found, key=lambda a: a.name) == [chase, joint]

    assert await repo.delete_by_ids([chase.id, joint.id]) == 2
    assert await repo.delete_by_ids([]) == 0
    await db_session.commit()
    assert await repo.get_all() == [amex]
