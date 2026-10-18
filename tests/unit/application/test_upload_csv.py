from datetime import UTC, date, datetime
from decimal import Decimal
import hashlib
from unittest.mock import AsyncMock
import uuid

import pytest

from src.application.use_cases.upload_csv import UploadCsvCommand, UploadCsvUseCase
from src.domain.entities.account import joint_account_id, personal_account_id
from src.domain.entities.category import Category
from src.domain.entities.person import Person
from src.domain.exceptions import NotFoundError
from src.domain.filters import is_joint_row
from tests.fixtures.factories import (
    ALICE,
    BOB,
    make_category,
    make_joint_account,
    make_person,
    make_transaction,
    make_upload,
)
from tests.fixtures.mocks import make_mock_uow

VALID_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-50.00",shared\n'
    '2026-01-16,Gas Station,Gas,Chase,GAS STATION,,"-30.00",\n'
    '2026-01-17,Restaurant,Dining Out,Chase,RESTAURANT,,"-80.00","shared,s70"\n'
)


def _make_command(
    csv_text: str = VALID_CSV,
    person_id: uuid.UUID | None = None,
    accepted_change_ids: frozenset[uuid.UUID] = frozenset(),
) -> UploadCsvCommand:
    return UploadCsvCommand(
        data=csv_text.encode(),
        person_id=person_id or uuid.uuid4(),
        filename="test.csv",
        accepted_change_ids=accepted_change_ids,
    )


async def test_uploads_all_new_transactions() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = [
        make_category(name="Groceries"),
        make_category(name="Gas"),
        make_category(name="Dining Out"),
    ]
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = []
    command = _make_command(person_id=person.id)

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.new_count == 3
    assert result.updated_count == 0
    assert result.skipped_count == 0
    assert result.unmapped_categories == []
    uow.uploads.save.assert_called_once()
    uow.transactions.save_batch.assert_called_once()
    uow.commit.assert_called_once()
    # No new categories to auto-create
    uow.categories.save_batch.assert_not_called()


async def test_skips_unchanged_transactions() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = []
    existing = make_transaction(
        payer_person_id=person.id,
        original_statement="GROCERY STORE",
        account="Chase",
        merchant="Grocery Store",
        category="Groceries",
        amount=Decimal("-50.00"),
        tags=("shared",),
        payer_percentage=50,
        notes="",
    )
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [
        existing
    ]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        f'{existing.date.isoformat()},Grocery Store,Groceries,Chase,GROCERY STORE,,"{existing.amount}",shared\n'
    )
    command = _make_command(csv_text=csv, person_id=person.id)

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.new_count == 0
    assert result.updated_count == 0
    assert result.skipped_count == 1
    uow.transactions.save_batch.assert_not_called()


async def test_updates_accepted_changes() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = []
    existing = make_transaction(
        payer_person_id=person.id,
        original_statement="GROCERY STORE",
        account="Chase",
        merchant="Old Name",
        category="Groceries",
        amount=Decimal("-50.00"),
        tags=("shared",),
        payer_percentage=50,
        notes="",
    )
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [
        existing
    ]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        f'{existing.date.isoformat()},New Name,Groceries,Chase,GROCERY STORE,,"{existing.amount}",shared\n'
    )
    command = _make_command(
        csv_text=csv,
        person_id=person.id,
        accepted_change_ids=frozenset({existing.id}),
    )

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.new_count == 0
    assert result.updated_count == 1
    assert result.skipped_count == 0
    uow.transactions.update_mutable_fields_batch.assert_called_once()
    batch = uow.transactions.update_mutable_fields_batch.call_args[0][0]
    assert len(batch) == 1


async def test_skips_rejected_changes() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = []
    existing = make_transaction(
        payer_person_id=person.id,
        original_statement="GROCERY STORE",
        account="Chase",
        merchant="Old Name",
        category="Groceries",
        amount=Decimal("-50.00"),
        tags=("shared",),
        payer_percentage=50,
        notes="",
    )
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [
        existing
    ]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        f'{existing.date.isoformat()},New Name,Groceries,Chase,GROCERY STORE,,"{existing.amount}",shared\n'
    )
    # No accepted_change_ids → reject the change
    command = _make_command(csv_text=csv, person_id=person.id)

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.new_count == 0
    assert result.updated_count == 0
    assert result.skipped_count == 1
    uow.transactions.update_mutable_fields.assert_not_called()


async def test_date_edited_row_still_matches_by_original_date() -> None:
    """A row whose date was edited in-app past the CSV window is fetched via
    original_date and classified unchanged — not re-inserted as a duplicate."""
    from datetime import date

    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = []
    # CSV row dated Jan 15; the stored twin was moved to Feb 20 in-app,
    # keeping original_date = Jan 15 (what the CSV still says).
    existing = make_transaction(
        payer_person_id=person.id,
        date=date(2026, 2, 20),
        original_date=date(2026, 1, 15),
        original_statement="GROCERY STORE",
        account="Chase",
        merchant="Grocery Store",
        category="Groceries",
        amount=Decimal("-50.00"),
        tags=("shared",),
        payer_percentage=50,
        notes="",
    )
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [
        existing
    ]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-50.00",shared\n'
    )
    command = _make_command(csv_text=csv, person_id=person.id)

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.new_count == 0
    assert result.skipped_count == 1
    uow.transactions.save_batch.assert_not_called()
    # The dedup fetch window is min/max of the incoming CSV dates, over the
    # accounts the file names.
    uow.transactions.get_by_account_ids_and_original_date_range.assert_called_once_with(
        [personal_account_id(person.id, "Chase")], date(2026, 1, 15), date(2026, 1, 15)
    )


async def test_auto_creates_unmapped_categories_on_upload() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.categories.get_all.return_value = [
        make_category(name="Groceries"),
    ]
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = []
    command = _make_command()

    result = await UploadCsvUseCase().execute(command, uow)

    # "Dining Out" and "Gas" are new → auto-created with group_id=None
    uow.categories.save_batch.assert_called_once()
    saved = uow.categories.save_batch.call_args[0][0]
    saved_cats = sorted(c.name for c in saved)
    assert saved_cats == ["Dining Out", "Gas"]
    assert all(c.group_id is None for c in saved)
    # They should be reported as unmapped
    assert result.unmapped_categories == ["Dining Out", "Gas"]


async def test_reports_existing_unmapped_categories() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.categories.get_all.return_value = [
        make_category(name="Groceries"),
        Category(id=uuid.uuid4(), name="Gas", group_id=None),
        Category(id=uuid.uuid4(), name="Dining Out", group_id=None),
    ]
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = []
    command = _make_command()

    result = await UploadCsvUseCase().execute(command, uow)

    # No new categories to create
    uow.categories.save_batch.assert_not_called()
    # But existing unmapped ones are reported
    assert result.unmapped_categories == ["Dining Out", "Gas"]


async def test_raises_not_found_for_missing_person() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = None
    command = _make_command()

    with pytest.raises(NotFoundError, match="Person"):
        await UploadCsvUseCase().execute(command, uow)


async def test_handles_empty_csv() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.categories.get_all.return_value = []
    csv_text = "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    command = _make_command(csv_text=csv_text)

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.new_count == 0
    assert result.updated_count == 0
    assert result.skipped_count == 0
    uow.transactions.save_batch.assert_not_called()


async def test_adjustment_rows_not_imported() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = []

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-50.00",shared\n'
        '2026-01-16,Adjustment,Groceries,Adj,ADJ,,"25.00",couplefins-adjustment\n'
    )
    command = _make_command(csv_text=csv, person_id=person.id)

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.new_count == 1
    assert result.skipped_adjustment_count == 1
    saved = uow.transactions.save_batch.call_args[0][0]
    assert [tx.merchant for tx in saved] == ["Grocery Store"]


async def test_reupload_deletes_rows_missing_from_csv() -> None:
    """Rows in the window that the new CSV no longer contains are deleted."""
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = []
    kept = make_transaction(
        payer_person_id=person.id,
        original_statement="GROCERY STORE",
        account="Chase",
        merchant="Grocery Store",
        category="Groceries",
        amount=Decimal("-50.00"),
        tags=("shared",),
        payer_percentage=50,
        notes="",
    )
    dropped = make_transaction(
        payer_person_id=person.id,
        original_statement="COFFEE SHOP",
        account="Chase",
        merchant="Coffee Shop",
        date=kept.date,
    )
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [
        kept,
        dropped,
    ]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        f'{kept.date.isoformat()},Grocery Store,Groceries,Chase,GROCERY STORE,,"{kept.amount}",shared\n'
    )
    command = _make_command(csv_text=csv, person_id=person.id)

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.removed_count == 1
    assert result.warnings == []
    assert result.skipped_count == 1
    uow.transactions.delete_by_ids.assert_called_once_with([dropped.id])
    uow.transaction_edits.delete_by_transaction_ids.assert_called_once_with([
        dropped.id
    ])
    uow.commit.assert_called_once()


async def test_removed_settlement_linked_row_unlinks_with_warning() -> None:
    from tests.fixtures.factories import make_settlement_transaction_link

    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = []
    dropped = make_transaction(
        payer_person_id=person.id,
        original_statement="VENMO PAYMENT",
        account="Chase",
        merchant="Venmo",
    )
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [dropped]
    uow.settlement_transaction_links.get_by_transaction_ids.return_value = [
        make_settlement_transaction_link(transaction_id=dropped.id)
    ]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        f'{dropped.date.isoformat()},Grocery Store,Groceries,Chase,GROCERY STORE,,"-50.00",shared\n'
    )
    command = _make_command(csv_text=csv, person_id=person.id)

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.removed_count == 1
    assert len(result.warnings) == 1
    assert "Venmo" in result.warnings[0]
    assert "linked to a settlement" in result.warnings[0]
    uow.settlement_transaction_links.delete_by_transaction_ids.assert_called_once_with([
        dropped.id
    ])
    uow.transactions.delete_by_ids.assert_called_once_with([dropped.id])


async def test_a_removed_row_that_paid_an_obligation_warns() -> None:
    """The database clears the obligation's paying row, so it is unpaid
    again; the warning says so."""
    from tests.fixtures.factories import make_obligation

    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = []
    dropped = make_transaction(
        payer_person_id=person.id, account="Chase", merchant="County Tax Office"
    )
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [dropped]
    uow.obligations.get_by_paid_transaction_ids.return_value = [
        make_obligation(paid_by_transaction_id=dropped.id)
    ]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        f'{dropped.date.isoformat()},Grocery Store,Groceries,Chase,GROCERY STORE,,"-50.00",shared\n'
    )
    command = _make_command(csv_text=csv, person_id=person.id)

    result = await UploadCsvUseCase().execute(command, uow)

    assert len(result.warnings) == 1
    assert "County Tax Office" in result.warnings[0]
    assert "paid an obligation" in result.warnings[0]
    uow.obligations.get_by_paid_transaction_ids.assert_awaited_once_with([dropped.id])
    uow.settlement_transaction_links.delete_by_transaction_ids.assert_not_called()
    uow.transactions.delete_by_ids.assert_called_once_with([dropped.id])


async def test_rejects_removal_from_finalized_month() -> None:
    """A removed row's own month is guarded even when no incoming row is in it."""
    from datetime import date

    from src.domain.exceptions import PeriodFinalizedError
    from tests.fixtures.factories import make_reconciliation_period

    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = []
    # Removal candidate whose date was edited into finalized February;
    # original_date keeps it inside the January upload window.
    dropped = make_transaction(
        payer_person_id=person.id,
        date=date(2026, 2, 10),
        original_date=date(2026, 1, 16),
        original_statement="COFFEE SHOP",
        account="Chase",
    )
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [dropped]
    uow.reconciliation_periods.get_by_periods.return_value = [
        make_reconciliation_period(
            year=2026, month=2, is_finalized=True, finalized_at=datetime.now(UTC)
        )
    ]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-50.00",shared\n'
    )
    command = _make_command(csv_text=csv, person_id=person.id)

    with pytest.raises(PeriodFinalizedError, match="2026-02"):
        await UploadCsvUseCase().execute(command, uow)

    checked = uow.reconciliation_periods.get_by_periods.call_args[0][0]
    assert {(2026, 1), (2026, 2)} <= checked
    uow.transactions.delete_by_ids.assert_not_called()
    uow.commit.assert_not_called()


async def test_rejects_accepted_change_to_finalized_month() -> None:
    """An accepted 'changed' row is guarded by its CURRENT month, not the CSV's.

    The row's date was edited into finalized February; original_date keeps it
    inside the January upload window, so it pairs with the CSV twin and would
    be updated in place — mutating a locked month unless the guard catches it.
    """
    from datetime import date

    from src.domain.exceptions import PeriodFinalizedError
    from tests.fixtures.factories import make_reconciliation_period

    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.categories.get_all.return_value = []
    edited = make_transaction(
        payer_person_id=person.id,
        date=date(2026, 2, 10),
        original_date=date(2026, 1, 15),
        original_statement="GROCERY STORE",
        account="Chase",
        merchant="Old Name",
        category="Groceries",
        amount=Decimal("-50.00"),
        tags=("shared",),
        payer_percentage=50,
        notes="",
    )
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [edited]
    uow.reconciliation_periods.get_by_periods.return_value = [
        make_reconciliation_period(
            year=2026, month=2, is_finalized=True, finalized_at=datetime.now(UTC)
        )
    ]

    # Same natural key (date/amount/account/statement), changed merchant.
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,New Name,Groceries,Chase,GROCERY STORE,,"-50.00",shared\n'
    )
    command = _make_command(
        csv_text=csv,
        person_id=person.id,
        accepted_change_ids=frozenset({edited.id}),
    )

    with pytest.raises(PeriodFinalizedError, match="2026-02"):
        await UploadCsvUseCase().execute(command, uow)

    checked = uow.reconciliation_periods.get_by_periods.call_args[0][0]
    assert {(2026, 1), (2026, 2)} <= checked
    uow.transactions.update_mutable_fields_batch.assert_not_called()
    uow.commit.assert_not_called()


async def test_rejects_upload_to_finalized_month() -> None:

    from src.domain.exceptions import PeriodFinalizedError
    from tests.fixtures.factories import make_reconciliation_period

    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.categories.get_all.return_value = []
    uow.reconciliation_periods.get_by_periods.return_value = [
        make_reconciliation_period(
            year=2026, month=1, is_finalized=True, finalized_at=datetime.now(UTC)
        )
    ]
    command = _make_command()

    with pytest.raises(PeriodFinalizedError, match="2026-01"):
        await UploadCsvUseCase().execute(command, uow)

    uow.commit.assert_not_called()


async def test_records_importer_and_file_hash() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = []

    await UploadCsvUseCase().execute(_make_command(person_id=person.id), uow)

    upload = uow.uploads.save.call_args.args[0]
    assert upload.importer == "monarch_csv"
    assert upload.content_sha256 == hashlib.sha256(VALID_CSV.encode()).hexdigest()


async def test_adds_the_account_each_new_row_names() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = []

    await UploadCsvUseCase().execute(_make_command(person_id=person.id), uow)

    (accounts,) = uow.accounts.add_missing.call_args.args
    chase = personal_account_id(person.id, "Chase")
    assert [(a.id, a.name, a.owner_person_id) for a in accounts] == [
        (chase, "Chase", person.id)
    ]
    saved = uow.transactions.save_batch.call_args.args[0]
    assert {tx.account_id for tx in saved} == {chase}


async def test_adds_no_accounts_when_no_row_is_new() -> None:
    uow = make_mock_uow()
    person = make_person()
    uow.persons.get_by_id.return_value = person
    existing = make_transaction(
        payer_person_id=person.id,
        original_statement="GROCERY STORE",
        account="Chase",
        merchant="Grocery Store",
        category="Groceries",
        amount=Decimal("-50.00"),
        tags=("shared",),
        payer_percentage=50,
    )
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [
        existing
    ]
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-50.00",shared\n'
    )

    await UploadCsvUseCase().execute(
        _make_command(csv_text=csv, person_id=person.id), uow
    )

    uow.accounts.add_missing.assert_not_called()


JOINT_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-15,Hardware Store,Home Improvement,Joint Checking,HARDWARE STORE,,"-120.00",shared\n'
    '2026-01-16,Grocery Store,Groceries,Chase,GROCERY STORE,,"-50.00",\n'
)


ALICE_UPLOAD = make_upload(person_id=ALICE.id)


def _joint_uow(uploader: Person) -> AsyncMock:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = uploader
    uow.persons.get_all.return_value = [ALICE, BOB]
    uow.accounts.get_all.return_value = [make_joint_account("Joint Checking")]
    uow.uploads.get_by_ids.return_value = [ALICE_UPLOAD]
    return uow


async def test_rows_on_a_joint_label_import_into_the_joint_account() -> None:
    """US-IMPORT-5: no payer, household, unsplit, outside settlement."""
    uow = _joint_uow(ALICE)

    await UploadCsvUseCase().execute(_make_command(JOINT_CSV, ALICE.id), uow)

    saved = uow.transactions.save_batch.call_args.args[0]
    [hardware] = [tx for tx in saved if tx.account == "Joint Checking"]
    assert is_joint_row(hardware)
    assert hardware.account_id == joint_account_id("Joint Checking")
    assert (hardware.payer_percentage, hardware.household) == (100, True)
    # The joint account exists already; only the personal account is added.
    (accounts,) = uow.accounts.add_missing.call_args.args
    assert [a.name for a in accounts] == ["Chase"]


async def test_partner_upload_of_the_same_joint_rows_adds_nothing() -> None:
    """US-IMPORT-5: both partners' exports of a joint row store it once."""
    uow = _joint_uow(BOB)
    alice_import = make_transaction(
        joint=True,
        upload_id=ALICE_UPLOAD.id,
        account="Joint Checking",
        date=date(2026, 1, 15),
        merchant="Hardware Store",
        category="Home Improvement",
        original_statement="HARDWARE STORE",
        amount=Decimal("-120.00"),
        tags=("shared",),
        notes="",
    )
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [
        alice_import
    ]
    joint_only = "\n".join(JOINT_CSV.splitlines()[:2]) + "\n"

    result = await UploadCsvUseCase().execute(_make_command(joint_only, BOB.id), uow)

    assert (result.new_count, result.skipped_count, result.removed_count) == (0, 1, 0)
    uow.transactions.save_batch.assert_not_called()
    uow.accounts.get_all.assert_awaited_once()
    (account_ids, *_) = (
        uow.transactions.get_by_account_ids_and_original_date_range.call_args.args
    )
    assert joint_account_id("Joint Checking") in account_ids


async def test_file_not_naming_the_joint_account_leaves_it_alone() -> None:
    """US-IMPORT-5: the removal scope is the uploader's personal accounts
    plus the accounts the file names, so a joint row is never a removal
    candidate unless the file names its account."""
    uow = _joint_uow(ALICE)
    chase_only = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-16,Grocery Store,Groceries,Chase,GROCERY STORE,,"-50.00",\n'
    )

    await UploadCsvUseCase().execute(_make_command(chase_only, ALICE.id), uow)

    (account_ids, *_) = (
        uow.transactions.get_by_account_ids_and_original_date_range.call_args.args
    )
    assert account_ids == [personal_account_id(ALICE.id, "Chase")]
    uow.transactions.delete_by_ids.assert_not_called()


async def test_partners_file_lacking_a_joint_row_the_other_imported_removes_nothing() -> (
    None
):
    """US-IMPORT-5: a joint row is removed only by its own uploader's re-import."""
    uow = _joint_uow(BOB)
    alices = make_transaction(
        joint=True,
        upload_id=ALICE_UPLOAD.id,
        account="Joint Checking",
        date=date(2026, 1, 15),
        original_statement="PAINT STORE",
    )
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [alices]
    joint_only = "\n".join(JOINT_CSV.splitlines()[:2]) + "\n"

    result = await UploadCsvUseCase().execute(_make_command(joint_only, BOB.id), uow)

    assert result.removed_count == 0
    uow.transactions.delete_by_ids.assert_not_called()


async def test_uploaders_later_file_lacking_their_joint_row_removes_it() -> None:
    uow = _joint_uow(ALICE)
    alices = make_transaction(
        joint=True,
        upload_id=ALICE_UPLOAD.id,
        account="Joint Checking",
        date=date(2026, 1, 15),
        original_statement="PAINT STORE",
    )
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [alices]
    joint_only = "\n".join(JOINT_CSV.splitlines()[:2]) + "\n"

    result = await UploadCsvUseCase().execute(_make_command(joint_only, ALICE.id), uow)

    assert result.removed_count == 1
    uow.transactions.delete_by_ids.assert_awaited_once_with([alices.id])
