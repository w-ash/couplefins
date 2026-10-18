from datetime import UTC, date, datetime
from decimal import Decimal

import attrs
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.co_owned_asset import CoOwnedAsset
from src.infrastructure.persistence.repositories.co_owned_asset_repository import (
    CoOwnedAssetRepository,
)
from src.infrastructure.persistence.repositories.loan_repository import (
    LoanRepository,
)
from tests.fixtures.factories import make_co_owned_asset, make_loan


async def _asset(session: AsyncSession) -> CoOwnedAsset:
    asset = make_co_owned_asset()
    await CoOwnedAssetRepository(session).save(asset)
    return asset


async def test_a_loan_round_trips(db_session: AsyncSession) -> None:
    asset = await _asset(db_session)
    repo = LoanRepository(db_session)
    loan = make_loan(
        asset_id=asset.id,
        kind="interest_only",
        annual_rate=Decimal("8.500"),
        term_months=None,
        notes="Example note",
        created_at=datetime(2026, 10, 17, 9, 30, tzinfo=UTC),
    )

    await repo.save(loan)
    await db_session.commit()

    assert await repo.get_by_id(loan.id) == loan
    assert await repo.get_by_slug("mortgage") == loan
    assert await repo.get_by_slug("other") is None


async def test_a_replaced_loan_keeps_its_link_and_the_list_keeps_order(
    db_session: AsyncSession,
) -> None:
    asset = await _asset(db_session)
    repo = LoanRepository(db_session)
    old = make_loan(
        asset_id=asset.id,
        name="Bridge loan",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    new = make_loan(asset_id=asset.id, created_at=datetime(2026, 4, 1, tzinfo=UTC))
    replaced = attrs.evolve(
        old, closed_on=date(2026, 3, 31), replaced_by_loan_id=new.id
    )

    await repo.save(old)
    await repo.save_batch([new, replaced])
    await db_session.commit()

    assert await repo.get_by_asset_id(asset.id) == [replaced, new]
    assert await repo.get_by_ids([new.id]) == [new]
    assert await repo.get_by_asset_id(make_co_owned_asset().id) == []
    assert await repo.exists_replaced_by(new.id) is True
    assert await repo.exists_replaced_by(old.id) is False


async def test_a_slug_is_unique(db_session: AsyncSession) -> None:
    asset = await _asset(db_session)
    repo = LoanRepository(db_session)
    await repo.save(make_loan(asset_id=asset.id))

    with pytest.raises(IntegrityError):
        await repo.save(make_loan(asset_id=asset.id, name="Mortgage!"))


async def test_delete_removes_the_loan(db_session: AsyncSession) -> None:
    asset = await _asset(db_session)
    repo = LoanRepository(db_session)
    loan = make_loan(asset_id=asset.id)
    await repo.save(loan)

    assert await repo.delete(loan.id) is True
    assert await repo.get_by_id(loan.id) is None
