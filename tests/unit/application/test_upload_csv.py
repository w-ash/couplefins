from decimal import Decimal
import uuid

import pytest

from src.application.use_cases.upload_csv import UploadCsvCommand, UploadCsvUseCase
from src.domain.entities.category import Category
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import (
    make_category,
    make_person,
    make_transaction,
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
        csv_text=csv_text,
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
    uow.transactions.get_by_person_and_original_date_range.return_value = []
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
    uow.transactions.get_by_person_and_original_date_range.return_value = [existing]

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
    uow.transactions.get_by_person_and_original_date_range.return_value = [existing]

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
    uow.transactions.get_by_person_and_original_date_range.return_value = [existing]

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
    uow.transactions.get_by_person_and_original_date_range.return_value = [existing]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-50.00",shared\n'
    )
    command = _make_command(csv_text=csv, person_id=person.id)

    result = await UploadCsvUseCase().execute(command, uow)

    assert result.new_count == 0
    assert result.skipped_count == 1
    uow.transactions.save_batch.assert_not_called()
    # The dedup fetch window is min/max of the incoming CSV dates.
    uow.transactions.get_by_person_and_original_date_range.assert_called_once_with(
        person.id, date(2026, 1, 15), date(2026, 1, 15)
    )


async def test_auto_creates_unmapped_categories_on_upload() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = make_person()
    uow.categories.get_all.return_value = [
        make_category(name="Groceries"),
    ]
    uow.transactions.get_by_person_and_original_date_range.return_value = []
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
    uow.transactions.get_by_person_and_original_date_range.return_value = []
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
    uow.transactions.get_by_person_and_original_date_range.return_value = [
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
    uow.transactions.get_by_person_and_original_date_range.return_value = [dropped]
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


async def test_rejects_removal_from_finalized_month() -> None:
    """A removed row's own month is guarded even when no incoming row is in it."""
    from datetime import UTC, date, datetime

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
    uow.transactions.get_by_person_and_original_date_range.return_value = [dropped]
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
    from datetime import UTC, date, datetime

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
    uow.transactions.get_by_person_and_original_date_range.return_value = [edited]
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
    from datetime import UTC, datetime

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
