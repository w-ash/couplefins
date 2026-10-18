from datetime import date
from decimal import Decimal

import attrs
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.co_owned_asset import CoOwnedAsset
from src.domain.entities.loan import Loan
from src.infrastructure.persistence.repositories.co_owned_asset_repository import (
    CoOwnedAssetRepository,
)
from src.infrastructure.persistence.repositories.loan_repository import (
    LoanRepository,
)
from src.infrastructure.persistence.repositories.obligation_repository import (
    ObligationRepository,
)
from src.infrastructure.persistence.repositories.person_repository import (
    PersonRepository,
)
from src.infrastructure.persistence.repositories.transaction_repository import (
    TransactionRepository,
)
from src.infrastructure.persistence.repositories.upload_repository import (
    UploadRepository,
)
from tests.fixtures.factories import (
    make_co_owned_asset,
    make_loan,
    make_obligation,
    make_person,
    make_transaction,
    make_upload,
)
from tests.integration.seed import save_transactions


async def _asset_and_loan(session: AsyncSession) -> tuple[CoOwnedAsset, Loan]:
    asset = make_co_owned_asset()
    loan = make_loan(asset_id=asset.id)
    await CoOwnedAssetRepository(session).save(asset)
    await LoanRepository(session).save(loan)
    return asset, loan


async def test_obligations_round_trip_in_due_order(db_session: AsyncSession) -> None:
    asset, loan = await _asset_and_loan(db_session)
    repo = ObligationRepository(db_session)
    tax = make_obligation(
        asset_id=asset.id,
        amount=Decimal("2430.56"),
        is_estimate=True,
        due_on=date(2026, 11, 1),
        late_after=date(2026, 12, 10),
        pays_from="property-tax",
        notes="Bill not yet out",
    )
    payment = make_obligation(
        asset_id=asset.id, kind="loan_payment", loan_id=loan.id, due_on=date(2026, 5, 1)
    )

    await repo.save_batch([tax, payment])
    await db_session.commit()

    assert await repo.get_by_asset_id(asset.id) == [payment, tax]
    assert await repo.get_by_loan_id(loan.id) == [payment]
    assert await repo.get_by_id(tax.id) == tax
    assert await repo.get_by_ids([tax.id]) == [tax]


async def test_delete_and_delete_by_ids(db_session: AsyncSession) -> None:
    asset, _ = await _asset_and_loan(db_session)
    repo = ObligationRepository(db_session)
    first, second, third = (make_obligation(asset_id=asset.id) for _ in range(3))
    await repo.save_batch([first, second, third])

    assert await repo.delete(first.id) is True
    assert await repo.delete_by_ids([second.id, third.id]) == 2
    assert await repo.delete_by_ids([]) == 0
    assert await repo.get_by_asset_id(asset.id) == []


async def test_deleting_the_paying_row_leaves_the_obligation_unpaid(
    db_session: AsyncSession,
) -> None:
    asset, _ = await _asset_and_loan(db_session)
    alice = make_person(name="Alice")
    upload = make_upload(person_id=alice.id)
    await PersonRepository(db_session).save(alice)
    await UploadRepository(db_session).save(upload)
    [row] = await save_transactions(
        db_session,
        [make_transaction(upload_id=upload.id, payer_person_id=alice.id)],
    )
    repo = ObligationRepository(db_session)
    paid = make_obligation(asset_id=asset.id, paid_by_transaction_id=row.id)
    await repo.save_batch([paid, make_obligation(asset_id=asset.id)])
    await db_session.commit()
    assert await repo.get_by_paid_transaction_ids([row.id]) == [paid]
    assert await repo.get_by_paid_transaction_ids([]) == []

    await TransactionRepository(db_session).delete_by_ids([row.id])
    await db_session.commit()
    db_session.expunge_all()

    assert await repo.get_by_id(paid.id) == attrs.evolve(
        paid, paid_by_transaction_id=None
    )
