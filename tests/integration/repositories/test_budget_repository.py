from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.repositories.category_group_budget_repository import (
    CategoryGroupBudgetRepository,
)
from src.infrastructure.persistence.repositories.category_group_repository import (
    CategoryGroupRepository,
)
from src.infrastructure.persistence.repositories.person_repository import (
    PersonRepository,
)
from tests.fixtures.factories import (
    make_category_group,
    make_category_group_budget,
    make_person,
)


async def _seed_group(session: AsyncSession) -> str:
    group = make_category_group(name="Food & Dining")
    await CategoryGroupRepository(session).save(group)
    await session.commit()
    return str(group.id)


async def _seed_person(session: AsyncSession, name: str = "Alice") -> str:
    person = make_person(name=name)
    await PersonRepository(session).save(person)
    await session.commit()
    return str(person.id)


async def test_get_by_month_happy_path(db_session: AsyncSession) -> None:
    from uuid import UUID

    group_id = UUID(await _seed_group(db_session))
    repo = CategoryGroupBudgetRepository(db_session)

    budget = make_category_group_budget(
        group_id=group_id, year=2026, month=3, monthly_amount=Decimal("500.00")
    )
    await repo.save(budget)
    await db_session.commit()

    results = await repo.get_by_month(2026, 3, None)
    assert len(results) == 1
    assert results[0].group_id == group_id
    assert results[0].monthly_amount == Decimal("500.00")
    assert results[0].year == 2026
    assert results[0].month == 3


async def test_get_by_month_empty(db_session: AsyncSession) -> None:
    repo = CategoryGroupBudgetRepository(db_session)
    results = await repo.get_by_month(2026, 6, None)
    assert results == []


async def test_get_by_year_sparse(db_session: AsyncSession) -> None:
    from uuid import UUID

    group_id = UUID(await _seed_group(db_session))
    repo = CategoryGroupBudgetRepository(db_session)

    for month in [1, 3, 5]:
        b = make_category_group_budget(
            group_id=group_id, year=2026, month=month, monthly_amount=Decimal("400.00")
        )
        await repo.save(b)
    await db_session.commit()

    results = await repo.get_by_year(2026, None)
    assert len(results) == 3
    months = {r.month for r in results}
    assert months == {1, 3, 5}


async def test_get_by_year_empty(db_session: AsyncSession) -> None:
    repo = CategoryGroupBudgetRepository(db_session)
    results = await repo.get_by_year(2025, None)
    assert results == []


async def test_upsert_replaces_existing(db_session: AsyncSession) -> None:
    from uuid import UUID

    group_id = UUID(await _seed_group(db_session))
    repo = CategoryGroupBudgetRepository(db_session)

    original = make_category_group_budget(
        group_id=group_id, year=2026, month=1, monthly_amount=Decimal("500.00")
    )
    await repo.save(original)
    await db_session.commit()

    updated = make_category_group_budget(
        id=original.id,
        group_id=group_id,
        year=2026,
        month=1,
        monthly_amount=Decimal("700.00"),
    )
    await repo.save(updated)
    await db_session.commit()

    results = await repo.get_by_month(2026, 1, None)
    assert len(results) == 1
    assert results[0].monthly_amount == Decimal("700.00")


async def test_household_and_personal_coexist(db_session: AsyncSession) -> None:
    from uuid import UUID

    group_id = UUID(await _seed_group(db_session))
    person_id = UUID(await _seed_person(db_session))
    repo = CategoryGroupBudgetRepository(db_session)

    household = make_category_group_budget(
        group_id=group_id,
        year=2026,
        month=1,
        monthly_amount=Decimal("500.00"),
        person_id=None,
    )
    personal = make_category_group_budget(
        group_id=group_id,
        year=2026,
        month=1,
        monthly_amount=Decimal("200.00"),
        person_id=person_id,
    )
    await repo.save(household)
    await repo.save(personal)
    await db_session.commit()

    household_results = await repo.get_by_month(2026, 1, None)
    personal_results = await repo.get_by_month(2026, 1, person_id)

    assert len(household_results) == 1
    assert household_results[0].monthly_amount == Decimal("500.00")
    assert household_results[0].person_id is None

    assert len(personal_results) == 1
    assert personal_results[0].monthly_amount == Decimal("200.00")
    assert personal_results[0].person_id == person_id
