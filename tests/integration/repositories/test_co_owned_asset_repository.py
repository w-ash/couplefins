from datetime import UTC, date, datetime
from decimal import Decimal

import attrs
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.repositories.co_owned_asset_repository import (
    CoOwnedAssetRepository,
)
from tests.fixtures.factories import make_co_owned_asset


async def test_get_current_is_none_before_setup(db_session: AsyncSession) -> None:
    assert await CoOwnedAssetRepository(db_session).get_current() is None


async def test_an_asset_round_trips(db_session: AsyncSession) -> None:
    repo = CoOwnedAssetRepository(db_session)
    asset = make_co_owned_asset(
        name="Home",
        repair_threshold=Decimal("750.00"),
        qualifying_kinds=frozenset({"repair", "closing", "loan-interest"}),
        bank_balance=Decimal("1234.56"),
        bank_balance_as_of=date(2026, 10, 1),
        created_at=datetime(2026, 10, 16, 9, 30, tzinfo=UTC),
    )

    await repo.save(asset)
    await db_session.commit()

    assert await repo.get_current() == asset


async def test_saving_again_updates_the_one_asset(db_session: AsyncSession) -> None:
    repo = CoOwnedAssetRepository(db_session)
    asset = make_co_owned_asset()
    await repo.save(asset)
    await db_session.commit()

    updated = attrs.evolve(
        asset, name="Renamed", bank_balance=None, qualifying_kinds=frozenset()
    )
    await repo.save(updated)
    await db_session.commit()

    assert await repo.get_current() == updated
    assert await repo.count() == 1
