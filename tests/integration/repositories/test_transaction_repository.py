from datetime import date
from decimal import Decimal
from uuid import UUID

import attrs
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.account import joint_account_id
from src.domain.entities.person import Person
from src.domain.entities.transaction import Transaction
from src.domain.entities.upload import Upload
from src.domain.parsing.importer import accounts_named_by
from src.infrastructure.persistence.repositories.account_repository import (
    AccountRepository,
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
    make_joint_account,
    make_person,
    make_transaction,
    make_upload,
)
from tests.integration.seed import save_transactions


async def _seed_couple(session: AsyncSession) -> tuple[Person, Person, Upload]:
    """Alice and Bob, and an upload of Alice's."""
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    upload = make_upload(person_id=alice.id)
    persons = PersonRepository(session)
    await persons.save(alice)
    await persons.save(bob)
    await UploadRepository(session).save(upload)
    return alice, bob, upload


async def _save_joint(session: AsyncSession, *txs: Transaction) -> None:
    """Save joint rows with the joint accounts they belong to."""
    await AccountRepository(session).add_missing([
        make_joint_account(name) for name in {tx.account for tx in txs}
    ])
    await TransactionRepository(session).save_batch(list(txs))
    await session.commit()


async def _seed_household_transactions(session: AsyncSession) -> None:
    alice = make_person(name="Alice")
    upload = make_upload(person_id=alice.id)

    await PersonRepository(session).save(alice)
    await UploadRepository(session).save(upload)

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
    non_household_tx = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 20),
        payer_person_id=alice.id,
        payer_percentage=100,
        household=False,
        amount=Decimal("-30.00"),
    )

    await save_transactions(session, [jan_tx, feb_tx, non_household_tx])
    await session.commit()


async def test_household_by_date_range_returns_only_household(
    db_session: AsyncSession,
) -> None:
    repo = TransactionRepository(db_session)
    await _seed_household_transactions(db_session)

    result = await repo.get_household_by_date_range(date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].amount == Decimal("-100.00")
    assert result[0].household is True


async def test_household_by_date_range_excludes_out_of_range(
    db_session: AsyncSession,
) -> None:
    repo = TransactionRepository(db_session)
    await _seed_household_transactions(db_session)

    result = await repo.get_household_by_date_range(date(2026, 3, 1), date(2026, 3, 31))
    assert result == []


async def test_household_by_date_range_boundary_dates(
    db_session: AsyncSession,
) -> None:
    repo = TransactionRepository(db_session)
    alice = make_person(name="Alice")
    upload = make_upload(person_id=alice.id)

    await PersonRepository(db_session).save(alice)
    await UploadRepository(db_session).save(upload)

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

    await save_transactions(db_session, [start_tx, end_tx, before_tx, after_tx])
    await db_session.commit()

    result = await repo.get_household_by_date_range(date(2026, 1, 1), date(2026, 1, 31))
    ids = {tx.id for tx in result}
    assert start_tx.id in ids
    assert end_tx.id in ids
    assert before_tx.id not in ids
    assert after_tx.id not in ids


async def test_household_by_date_range_empty_db(db_session: AsyncSession) -> None:
    repo = TransactionRepository(db_session)
    result = await repo.get_household_by_date_range(date(2026, 1, 1), date(2026, 1, 31))
    assert result == []


async def test_get_by_account_ids_and_original_date_range_coalesces_dates(
    db_session: AsyncSession,
) -> None:
    """The dedup fetch spans every account asked for (the uploader's and a
    joint one) and matches on original_date-or-date."""
    repo = TransactionRepository(db_session)
    alice, bob, upload = await _seed_couple(db_session)
    joint_account = make_joint_account("Joint Checking")
    await AccountRepository(db_session).add_missing([joint_account])

    in_window = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 15),
        payer_person_id=alice.id,
        original_statement="IN WINDOW",
    )
    other_account = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 16),
        payer_person_id=alice.id,
        account="Amex",
        original_statement="OTHER ACCOUNT",
    )
    joint = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 17),
        joint=True,
        account="Joint Checking",
        original_statement="JOINT",
    )
    # Date edited out of the window in-app; original_date still inside.
    edited_out = make_transaction(
        upload_id=upload.id,
        date=date(2026, 2, 20),
        original_date=date(2026, 1, 10),
        payer_person_id=alice.id,
        original_statement="EDITED OUT",
    )
    outside = make_transaction(
        upload_id=upload.id,
        date=date(2026, 2, 5),
        payer_person_id=alice.id,
        original_statement="OUTSIDE",
    )
    other_person = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 20),
        payer_person_id=bob.id,
        original_statement="OTHER PERSON",
    )
    await save_transactions(
        db_session,
        [in_window, other_account, joint, edited_out, outside, other_person],
    )
    await db_session.commit()

    result = await repo.get_by_account_ids_and_original_date_range(
        [in_window.account_id, other_account.account_id, joint_account.id],
        date(2026, 1, 1),
        date(2026, 1, 31),
    )

    assert {tx.id for tx in result} == {
        in_window.id,
        other_account.id,
        joint.id,
        edited_out.id,
    }
    assert (
        await repo.get_by_account_ids_and_original_date_range(
            [], date(2026, 1, 1), date(2026, 1, 31)
        )
        == []
    )


async def test_get_by_person_and_date_range_includes_beneficiary_rows(
    db_session: AsyncSession,
) -> None:
    """A non-household row someone else paid reaches the beneficiary's
    personal scope whenever payer_percentage < 100 (their share is nonzero)
    — e.g. a spotted front. A wholly personal row (pct=100) stays payer-only
    (v1.7.2)."""
    repo = TransactionRepository(db_session)
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    upload = make_upload(person_id=alice.id)

    persons = PersonRepository(db_session)
    await persons.save(alice)
    await persons.save(bob)
    await UploadRepository(db_session).save(upload)

    spotted = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 10),
        payer_person_id=alice.id,
        payer_percentage=0,
        household=False,
        tags=("bob",),
        original_statement="SPOTTED",
    )
    alice_own = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 12),
        payer_person_id=alice.id,
        payer_percentage=100,
        household=False,
        tags=(),
        original_statement="ALICE OWN",
    )
    await save_transactions(db_session, [spotted, alice_own])
    await db_session.commit()

    bob_rows = await repo.get_by_person_and_date_range(
        bob.id, date(2026, 1, 1), date(2026, 1, 31)
    )
    bob_ids = {tx.id for tx in bob_rows}
    assert spotted.id in bob_ids
    assert alice_own.id not in bob_ids

    alice_rows = await repo.get_by_person_and_date_range(
        alice.id, date(2026, 1, 1), date(2026, 1, 31)
    )
    alice_ids = {tx.id for tx in alice_rows}
    assert spotted.id in alice_ids
    assert alice_own.id in alice_ids


async def _seed_flagged_transaction(session: AsyncSession):
    """One saved transaction with both in-app flags set (linked + excluded)."""
    alice = make_person(name="Alice")
    upload = make_upload(person_id=alice.id)
    await PersonRepository(session).save(alice)
    await UploadRepository(session).save(upload)

    tx = make_transaction(
        upload_id=upload.id,
        payer_person_id=alice.id,
        merchant="Venmo",
        is_settlement=True,
        is_excluded=True,
    )
    await save_transactions(session, [tx])
    await session.commit()
    return tx


async def test_update_mutable_fields_batch_preserves_in_app_flags(
    db_session: AsyncSession,
) -> None:
    """Accepting a re-upload "changed" row must not revert is_settlement/is_excluded."""
    repo = TransactionRepository(db_session)
    tx = await _seed_flagged_transaction(db_session)

    # A freshly parsed CSV row carries default flags (False) and a new merchant.
    reparsed = attrs.evolve(
        tx, merchant="Venmo Payment", is_settlement=False, is_excluded=False
    )
    await repo.update_mutable_fields_batch([reparsed])
    await db_session.commit()

    stored = await repo.get_by_id(tx.id)
    assert stored is not None
    assert stored.merchant == "Venmo Payment"
    assert stored.is_settlement is True
    assert stored.is_excluded is True


async def test_update_mutable_fields_still_writes_in_app_flags(
    db_session: AsyncSession,
) -> None:
    """The singular update serves mark/unlink flows — it must flip the flags."""
    repo = TransactionRepository(db_session)
    tx = await _seed_flagged_transaction(db_session)

    unmarked = attrs.evolve(tx, is_settlement=False, is_excluded=False)
    await repo.update_mutable_fields(unmarked)
    await db_session.commit()

    stored = await repo.get_by_id(tx.id)
    assert stored is not None
    assert stored.is_settlement is False
    assert stored.is_excluded is False


async def test_get_all_settlement_relevant_spans_months_and_types(
    db_session: AsyncSession,
) -> None:
    """The all-time ledger fetch returns every split row regardless of date
    or household flag — shared, spotted, and personal splits — and excludes
    settlement transfers, excluded rows, and unsplit (pct=100) rows."""
    repo = TransactionRepository(db_session)
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    upload = make_upload(person_id=alice.id)

    persons = PersonRepository(db_session)
    await persons.save(alice)
    await persons.save(bob)
    await UploadRepository(db_session).save(upload)

    shared_jan = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 15),
        payer_person_id=alice.id,
        payer_percentage=50,
    )
    spotted_mar = make_transaction(
        upload_id=upload.id,
        date=date(2026, 3, 10),
        payer_person_id=alice.id,
        payer_percentage=0,
        household=False,
        tags=("bob",),
    )
    personal_split_prev_year = make_transaction(
        upload_id=upload.id,
        date=date(2025, 11, 2),
        payer_person_id=bob.id,
        payer_percentage=70,
        household=False,
        tags=("s70",),
    )
    unsplit = make_transaction(
        upload_id=upload.id,
        date=date(2026, 1, 20),
        payer_person_id=alice.id,
        payer_percentage=100,
        household=True,
    )
    settlement_transfer = make_transaction(
        upload_id=upload.id,
        date=date(2026, 2, 1),
        payer_person_id=alice.id,
        payer_percentage=50,
        is_settlement=True,
    )
    excluded = make_transaction(
        upload_id=upload.id,
        date=date(2026, 2, 12),
        payer_person_id=alice.id,
        payer_percentage=50,
        is_excluded=True,
    )
    await save_transactions(
        db_session,
        [
            shared_jan,
            spotted_mar,
            personal_split_prev_year,
            unsplit,
            settlement_transfer,
            excluded,
        ],
    )
    await db_session.commit()

    result = await repo.get_all_settlement_relevant()

    ids = {tx.id for tx in result}
    assert ids == {shared_jan.id, spotted_mar.id, personal_split_prev_year.id}


async def test_get_all_settlement_relevant_empty_db(db_session: AsyncSession) -> None:
    repo = TransactionRepository(db_session)
    assert await repo.get_all_settlement_relevant() == []


async def test_latest_household_date_skips_excluded_categories(
    db_session: AsyncSession,
) -> None:
    """A household card payment dated after the last dinner must not move
    the latest date once its category is excluded; with nothing excluded
    it is the newest row."""
    repo = TransactionRepository(db_session)
    alice = make_person(name="Alice")
    upload = make_upload(person_id=alice.id)
    await PersonRepository(db_session).save(alice)
    await UploadRepository(db_session).save(upload)

    dinner = make_transaction(
        upload_id=upload.id, date=date(2026, 1, 20), payer_person_id=alice.id
    )
    card_payment = make_transaction(
        upload_id=upload.id,
        date=date(2026, 2, 3),
        category="Credit Card Payment",
        payer_person_id=alice.id,
    )
    await save_transactions(db_session, [dinner, card_payment])
    await db_session.commit()

    assert await repo.get_latest_household_transaction_date(
        excluding_categories={"Credit Card Payment"}
    ) == date(2026, 1, 20)
    assert await repo.get_latest_household_transaction_date(
        excluding_categories=frozenset()
    ) == date(2026, 2, 3)


async def test_latest_household_date_scoped_to_a_year(
    db_session: AsyncSession,
) -> None:
    """A named year anchors on its own latest month, not the newest overall."""
    repo = TransactionRepository(db_session)
    alice = make_person(name="Alice")
    upload = make_upload(person_id=alice.id)
    await PersonRepository(db_session).save(alice)
    await UploadRepository(db_session).save(upload)

    await save_transactions(
        db_session,
        [
            make_transaction(
                upload_id=upload.id, date=date(2024, 11, 4), payer_person_id=alice.id
            ),
            make_transaction(
                upload_id=upload.id, date=date(2026, 1, 20), payer_person_id=alice.id
            ),
        ],
    )
    await db_session.commit()

    assert await repo.get_latest_household_transaction_date(
        excluding_categories=set(), year=2024
    ) == date(2024, 11, 4)
    assert await repo.get_latest_household_transaction_date(
        excluding_categories=set()
    ) == date(2026, 1, 20)
    assert (
        await repo.get_latest_household_transaction_date(
            excluding_categories=set(), year=2025
        )
        is None
    )


async def test_latest_household_date_empty_db(db_session: AsyncSession) -> None:
    repo = TransactionRepository(db_session)
    assert (
        await repo.get_latest_household_transaction_date(excluding_categories=set())
        is None
    )


# --- Joint rows ---


async def test_joint_row_round_trips_with_no_payer(db_session: AsyncSession) -> None:
    _, _, upload = await _seed_couple(db_session)
    joint = make_transaction(upload_id=upload.id, joint=True, account="Joint Checking")
    await _save_joint(db_session, joint)

    stored = await TransactionRepository(db_session).get_by_id(joint.id)

    assert stored == joint
    assert stored.payer_person_id is None
    assert stored.account_id == joint_account_id("Joint Checking")


async def test_owner_shares_and_depositor_round_trip(db_session: AsyncSession) -> None:
    alice, bob, upload = await _seed_couple(db_session)
    joint = make_transaction(
        upload_id=upload.id,
        joint=True,
        account="Joint Checking",
        amount=Decimal("500.00"),
        owner_shares={alice.id: 70, bob.id: 30},
        depositor_person_id=bob.id,
    )
    await _save_joint(db_session, joint)

    stored = await TransactionRepository(db_session).get_by_id(joint.id)

    assert stored is not None
    assert stored.owner_shares == {alice.id: 70, bob.id: 30}
    assert all(isinstance(k, UUID) for k in stored.owner_shares)
    assert stored.depositor_person_id == bob.id


async def test_settlement_reads_never_return_joint_rows(
    db_session: AsyncSession,
) -> None:
    alice, _, upload = await _seed_couple(db_session)
    split = make_transaction(
        upload_id=upload.id, payer_person_id=alice.id, payer_percentage=50
    )
    await save_transactions(db_session, [split])
    # A joint row with a split it should never have: the SQL filter still drops it.
    joint = attrs.evolve(
        make_transaction(upload_id=upload.id, joint=True, account="Joint Checking"),
        payer_percentage=50,
    )
    await _save_joint(db_session, joint)
    repo = TransactionRepository(db_session)

    assert [tx.id for tx in await repo.get_all_settlement_relevant()] == [split.id]
    assert [
        tx.id
        for tx in await repo.get_settlement_relevant_by_date_range(
            date(2026, 1, 1), date(2026, 1, 31)
        )
    ] == [split.id]


async def test_update_mutable_fields_batch_preserves_joint_assignments(
    db_session: AsyncSession,
) -> None:
    """A re-import never clears a joint row's hand-set depositor or shares."""
    alice, bob, upload = await _seed_couple(db_session)
    joint = make_transaction(
        upload_id=upload.id,
        joint=True,
        account="Joint Checking",
        owner_shares={alice.id: 60, bob.id: 40},
        depositor_person_id=alice.id,
    )
    await _save_joint(db_session, joint)
    repo = TransactionRepository(db_session)

    reparsed = attrs.evolve(
        joint, merchant="Renamed", owner_shares=None, depositor_person_id=None
    )
    await repo.update_mutable_fields_batch([reparsed])
    await db_session.commit()

    stored = await repo.get_by_id(joint.id)
    assert stored is not None
    assert stored.merchant == "Renamed"
    assert stored.owner_shares == {alice.id: 60, bob.id: 40}
    assert stored.depositor_person_id == alice.id


async def test_get_by_person_and_date_range_never_returns_joint_rows(
    db_session: AsyncSession,
) -> None:
    alice, _, upload = await _seed_couple(db_session)
    own = make_transaction(upload_id=upload.id, payer_person_id=alice.id)
    await save_transactions(db_session, [own])
    joint = make_transaction(upload_id=upload.id, joint=True, account="Joint Checking")
    await _save_joint(db_session, joint)

    result = await TransactionRepository(db_session).get_by_person_and_date_range(
        alice.id, date(2026, 1, 1), date(2026, 1, 31)
    )

    assert [tx.id for tx in result] == [own.id]


async def test_get_by_date_range_payer_only_leaves_out_joint_rows(
    db_session: AsyncSession,
) -> None:
    alice, _, upload = await _seed_couple(db_session)
    own = make_transaction(upload_id=upload.id, payer_person_id=alice.id)
    await save_transactions(db_session, [own])
    joint = make_transaction(upload_id=upload.id, joint=True, account="Joint Checking")
    await _save_joint(db_session, joint)
    repo = TransactionRepository(db_session)
    window = (date(2026, 1, 1), date(2026, 1, 31))

    payer_rows = await repo.get_by_date_range(*window, payer_only=True)
    every_row = await repo.get_by_date_range(*window)

    assert [tx.id for tx in payer_rows] == [own.id]
    assert {tx.id for tx in every_row} == {own.id, joint.id}


async def test_get_by_account_ids_returns_every_row_of_those_accounts(
    db_session: AsyncSession,
) -> None:
    alice, bob, upload = await _seed_couple(db_session)
    alice_chase = make_transaction(
        upload_id=upload.id, payer_person_id=alice.id, account="Chase"
    )
    alice_chase_later = make_transaction(
        upload_id=upload.id,
        payer_person_id=alice.id,
        account="Chase",
        date=date(2027, 6, 1),
    )
    bob_chase = make_transaction(
        upload_id=upload.id, payer_person_id=bob.id, account="Chase"
    )
    alice_amex = make_transaction(
        upload_id=upload.id, payer_person_id=alice.id, account="Amex"
    )
    await save_transactions(
        db_session, [alice_chase, alice_chase_later, bob_chase, alice_amex]
    )
    await db_session.commit()
    repo = TransactionRepository(db_session)

    result = await repo.get_by_account_ids([
        alice_chase.account_id,
        bob_chase.account_id,
    ])

    assert {tx.id for tx in result} == {
        alice_chase.id,
        alice_chase_later.id,
        bob_chase.id,
    }
    assert await repo.get_by_account_ids([]) == []


async def test_rekey_batch_moves_personal_rows_into_a_joint_account(
    db_session: AsyncSession,
) -> None:
    alice, _, upload = await _seed_couple(db_session)
    personal = make_transaction(
        upload_id=upload.id,
        payer_person_id=alice.id,
        account="Joint Checking",
        payer_percentage=50,
        household=False,
    )
    untouched = make_transaction(
        upload_id=upload.id, payer_person_id=alice.id, account="Chase"
    )
    await save_transactions(db_session, [personal, untouched])
    await AccountRepository(db_session).add_missing([
        make_joint_account("Joint Checking")
    ])
    await db_session.commit()
    repo = TransactionRepository(db_session)

    joint = attrs.evolve(
        personal,
        account_id=joint_account_id("Joint Checking"),
        payer_person_id=None,
        payer_percentage=100,
        household=True,
        is_settlement=True,
        depositor_person_id=alice.id,
        merchant="Ignored",
    )
    await repo.rekey_batch([joint])
    await db_session.commit()

    stored = await repo.get_by_id(personal.id)
    assert stored == attrs.evolve(joint, merchant=personal.merchant)
    assert await repo.get_by_id(untouched.id) == untouched


async def test_rekey_batch_back_to_personal_clears_joint_fields(
    db_session: AsyncSession,
) -> None:
    alice, bob, upload = await _seed_couple(db_session)
    joint = make_transaction(
        upload_id=upload.id,
        joint=True,
        account="Joint Checking",
        owner_shares={alice.id: 60, bob.id: 40},
    )
    await _save_joint(db_session, joint)
    personal = make_transaction(
        id=joint.id,
        upload_id=upload.id,
        payer_person_id=alice.id,
        account="Joint Checking",
    )
    await AccountRepository(db_session).add_missing(accounts_named_by([personal]))
    repo = TransactionRepository(db_session)

    await repo.rekey_batch([personal])
    await db_session.commit()

    stored = await repo.get_by_id(joint.id)
    assert stored is not None
    assert stored.payer_person_id == alice.id
    assert stored.owner_shares is None
    assert stored.account_id == personal.account_id
