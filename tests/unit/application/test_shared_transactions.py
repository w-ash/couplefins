from datetime import date
import uuid

import pytest

from src.application.use_cases._shared.transactions import (
    classify_against_existing,
    find_all_unmapped_categories,
    find_new_categories,
    find_unmapped_categories,
    joint_accounts,
    load_uploads,
)
from src.domain.entities.category import Category
from src.domain.entities.transaction import Transaction
from src.domain.entities.upload import MANUAL_IMPORTER
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import (
    ALICE,
    BOB,
    make_account,
    make_category,
    make_joint_account,
    make_transaction,
    make_upload,
)
from tests.fixtures.mocks import make_mock_uow


def test_find_new_categories_returns_unknown() -> None:
    categories = [
        make_category(name="Groceries"),
        make_category(name="Gas"),
    ]
    tx_cats = {"Groceries", "Gas", "Mystery"}
    assert find_new_categories(categories, tx_cats) == ["Mystery"]


def test_find_new_categories_empty_when_all_known() -> None:
    categories = [make_category(name="Groceries")]
    assert find_new_categories(categories, {"Groceries"}) == []


def test_find_new_categories_ignores_unmapped_in_db() -> None:
    categories = [Category(id=uuid.uuid4(), name="Groceries", group_id=None)]
    assert find_new_categories(categories, {"Groceries"}) == []


def test_find_unmapped_categories_returns_null_group() -> None:
    categories = [
        Category(id=uuid.uuid4(), name="Groceries", group_id=None),
        make_category(name="Gas"),
    ]
    tx_cats = {"Groceries", "Gas"}
    assert find_unmapped_categories(categories, tx_cats) == ["Groceries"]


def test_find_unmapped_categories_empty_when_all_mapped() -> None:
    categories = [make_category(name="Groceries")]
    assert find_unmapped_categories(categories, {"Groceries"}) == []


def test_find_unmapped_categories_ignores_absent_categories() -> None:
    categories = [Category(id=uuid.uuid4(), name="Groceries", group_id=None)]
    assert find_unmapped_categories(categories, {"Gas"}) == []


def test_find_all_unmapped_categories_combines_new_and_unmapped() -> None:
    categories = [
        Category(id=uuid.uuid4(), name="Groceries", group_id=None),
        make_category(name="Gas"),
    ]
    tx_cats = {"Groceries", "Gas", "Mystery"}
    assert find_all_unmapped_categories(categories, tx_cats) == ["Groceries", "Mystery"]


def test_find_all_unmapped_categories_empty_when_all_mapped() -> None:
    categories = [
        make_category(name="Groceries"),
        make_category(name="Gas"),
    ]
    assert find_all_unmapped_categories(categories, {"Groceries", "Gas"}) == []


async def test_load_uploads_reads_each_rows_upload_in_one_batch() -> None:
    uow = make_mock_uow()
    upload = make_upload(person_id=ALICE.id)
    uow.uploads.get_by_ids.return_value = [upload]
    rows = [make_transaction(upload_id=upload.id) for _ in range(3)]

    assert await load_uploads(uow, rows) == {upload.id: upload}
    uow.uploads.get_by_ids.assert_awaited_once_with([upload.id])


async def test_load_uploads_raises_for_a_missing_upload() -> None:
    uow = make_mock_uow()

    with pytest.raises(NotFoundError, match="Upload"):
        await load_uploads(uow, [make_transaction()])


async def test_load_uploads_of_no_rows_reads_nothing() -> None:
    uow = make_mock_uow()

    assert await load_uploads(uow, []) == {}
    uow.uploads.get_by_ids.assert_not_called()


# --- Re-import removal scope (US-IMPORT-5) ---

JOINT_LABEL = "Joint Checking"
ALICE_UPLOAD = make_upload(person_id=ALICE.id)
BOB_UPLOAD = make_upload(person_id=BOB.id)


def _joint_row(upload_id: uuid.UUID, statement: str) -> Transaction:
    return make_transaction(
        joint=True,
        account=JOINT_LABEL,
        upload_id=upload_id,
        date=date(2026, 1, 15),
        original_statement=statement,
    )


async def _removed(
    uploader: uuid.UUID, incoming: list[Transaction], existing: list[Transaction]
) -> list[Transaction]:
    uow = make_mock_uow()
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = existing
    uow.uploads.get_by_ids.return_value = [ALICE_UPLOAD, BOB_UPLOAD]
    accounts = [make_joint_account(JOINT_LABEL)]
    _, _, removed = await classify_against_existing(incoming, uploader, accounts, uow)
    return removed


async def test_a_partners_file_never_removes_a_joint_row_the_other_imported() -> None:
    alices = _joint_row(ALICE_UPLOAD.id, "HARDWARE STORE")
    bobs_file = [_joint_row(BOB_UPLOAD.id, "GROCERY STORE")]

    assert await _removed(BOB.id, bobs_file, [alices, *bobs_file]) == []


async def test_the_uploaders_later_file_removes_their_own_missing_joint_row() -> None:
    alices = _joint_row(ALICE_UPLOAD.id, "HARDWARE STORE")
    alices_later_file = [_joint_row(ALICE_UPLOAD.id, "GROCERY STORE")]

    removed = await _removed(ALICE.id, alices_later_file, [alices])

    assert removed == [alices]


async def test_the_uploaders_personal_rows_stay_removal_candidates() -> None:
    dinner = make_transaction(payer_person_id=ALICE.id, date=date(2026, 1, 15))
    alices_file = [_joint_row(ALICE_UPLOAD.id, "GROCERY STORE")]

    assert await _removed(ALICE.id, alices_file, [dinner]) == [dinner]


async def test_a_reimport_never_removes_a_hand_entered_row() -> None:
    """A manual upload is no import: the label's file never owns its rows,
    even when the person who entered them uploads it."""
    manual = make_upload(person_id=ALICE.id, importer=MANUAL_IMPORTER)
    entered = _joint_row(manual.id, "CLOSING COSTS")
    alices_file = [_joint_row(ALICE_UPLOAD.id, "GROCERY STORE")]
    uow = make_mock_uow()
    uow.transactions.get_by_account_ids_and_original_date_range.return_value = [entered]
    uow.uploads.get_by_ids.return_value = [manual, ALICE_UPLOAD]

    _, _, removed = await classify_against_existing(
        alices_file, ALICE.id, [make_joint_account(JOINT_LABEL)], uow
    )

    assert removed == []


def test_joint_accounts_keeps_only_the_joint_ones() -> None:
    joint = make_joint_account(JOINT_LABEL)

    assert joint_accounts([make_account(), joint]) == [joint]
