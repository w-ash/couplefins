import uuid

import pytest

from src.domain.entities.account import personal_account_id
from src.domain.exceptions import ValidationError
from src.domain.parsing.importer import ImportContext, accounts_named_by
from src.domain.parsing.monarch_csv import MonarchCsvImporter
from tests.fixtures.factories import make_transaction

CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    "2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,-50.00,shared\n"
    "2026-01-16,Gas Station,Gas,Chase,GAS STATION,,-30.00,\n"
    "2026-01-17,Bookshop,Shopping,Amex,BOOKSHOP,,-20.00,\n"
)


def _context(payer: uuid.UUID) -> ImportContext:
    return ImportContext(
        payer_person_id=payer, upload_id=uuid.uuid4(), person_names=frozenset()
    )


def test_personal_account_id_is_stable_per_owner_and_label() -> None:
    alice, bob = uuid.uuid4(), uuid.uuid4()

    assert personal_account_id(alice, "Chase") == personal_account_id(alice, "Chase")
    assert personal_account_id(alice, "Chase") != personal_account_id(alice, "Amex")
    assert personal_account_id(alice, "Chase") != personal_account_id(bob, "Chase")


def test_monarch_importer_points_each_row_at_its_payers_account() -> None:
    payer = uuid.uuid4()

    result = MonarchCsvImporter().parse(CSV.encode(), _context(payer))

    assert [tx.account_id for tx in result.transactions] == [
        personal_account_id(payer, "Chase"),
        personal_account_id(payer, "Chase"),
        personal_account_id(payer, "Amex"),
    ]


def test_accounts_named_by_gives_one_personal_account_per_account_id() -> None:
    payer = uuid.uuid4()
    chase = make_transaction(payer_person_id=payer, account="Chase")
    chase_again = make_transaction(payer_person_id=payer, account="Chase")
    amex = make_transaction(payer_person_id=payer, account="Amex")

    accounts = accounts_named_by([chase, chase_again, amex])

    assert [(a.id, a.name, a.kind, a.owner_person_id) for a in accounts] == [
        (chase.account_id, "Chase", "personal", payer),
        (amex.account_id, "Amex", "personal", payer),
    ]


def test_monarch_importer_accepts_a_byte_order_mark() -> None:
    result = MonarchCsvImporter().parse(
        b"\xef\xbb\xbf" + CSV.encode(), _context(uuid.uuid4())
    )

    assert len(result.transactions) == 3


def test_monarch_importer_rejects_non_utf8() -> None:
    with pytest.raises(ValidationError, match="not valid UTF-8"):
        MonarchCsvImporter().parse(b"\xff\xfe\x00bad", _context(uuid.uuid4()))
