from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.repositories.account_repository import (
    AccountRepository,
)
from src.infrastructure.persistence.repositories.person_repository import (
    PersonRepository,
)
from tests.fixtures.factories import make_account, make_person


async def test_get_by_owner_returns_only_that_persons_accounts(
    db_session: AsyncSession,
) -> None:
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    await PersonRepository(db_session).save_batch([alice, bob])
    chase = make_account(name="Chase", owner_person_id=alice.id)
    amex = make_account(name="Amex", owner_person_id=alice.id)
    bobs = make_account(name="Chase", owner_person_id=bob.id)
    joint = make_account(name="House", kind="joint")
    repo = AccountRepository(db_session)
    await repo.save_batch([chase, amex, bobs, joint])
    await db_session.commit()

    result = await repo.get_by_owner(alice.id)

    assert sorted(result, key=lambda a: a.name) == [amex, chase]


async def test_joint_account_round_trips(db_session: AsyncSession) -> None:
    joint = make_account(name="House", kind="joint")
    repo = AccountRepository(db_session)
    await repo.save_batch([joint])
    await db_session.commit()

    assert await repo.get_by_id(joint.id) == joint
