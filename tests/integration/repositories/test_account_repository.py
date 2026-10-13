from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.repositories.account_repository import (
    AccountRepository,
)
from src.infrastructure.persistence.repositories.person_repository import (
    PersonRepository,
)
from tests.fixtures.factories import make_account, make_person


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
