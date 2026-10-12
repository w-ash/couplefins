import uuid

import pytest

from src.domain.exceptions import ValidationError
from src.domain.parsing.importer import AccountResolver, ImportContext
from src.domain.parsing.monarch_csv import MonarchCsvImporter

CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    "2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,-50.00,shared\n"
    "2026-01-16,Gas Station,Gas,Chase,GAS STATION,,-30.00,\n"
    "2026-01-17,Bookshop,Shopping,Amex,BOOKSHOP,,-20.00,\n"
)


def _context(
    payer: uuid.UUID, accounts_by_label: dict[str, uuid.UUID] | None = None
) -> ImportContext:
    return ImportContext(
        payer_person_id=payer,
        upload_id=uuid.uuid4(),
        person_names=frozenset(),
        accounts_by_label=accounts_by_label or {},
    )


def test_resolver_returns_known_account() -> None:
    known = uuid.uuid4()
    resolver = AccountResolver(uuid.uuid4(), {"Chase": known})

    assert resolver.id_for("Chase") == known
    assert resolver.new_accounts == []


def test_resolver_creates_one_personal_account_per_new_label() -> None:
    owner = uuid.uuid4()
    resolver = AccountResolver(owner, {})

    first = resolver.id_for("Chase")
    again = resolver.id_for("Chase")

    assert first == again
    assert len(resolver.new_accounts) == 1
    account = resolver.new_accounts[0]
    assert (account.id, account.name, account.kind, account.owner_person_id) == (
        first,
        "Chase",
        "personal",
        owner,
    )


def test_monarch_importer_creates_accounts_for_new_labels() -> None:
    payer = uuid.uuid4()

    result = MonarchCsvImporter().parse(CSV.encode(), _context(payer))

    assert sorted(a.name for a in result.new_accounts) == ["Amex", "Chase"]
    ids = {a.name: a.id for a in result.new_accounts}
    assert [tx.account_id for tx in result.transactions] == [
        ids["Chase"],
        ids["Chase"],
        ids["Amex"],
    ]


def test_monarch_importer_reuses_the_uploaders_accounts() -> None:
    chase = uuid.uuid4()

    result = MonarchCsvImporter().parse(
        CSV.encode(), _context(uuid.uuid4(), {"Chase": chase})
    )

    assert [a.name for a in result.new_accounts] == ["Amex"]
    assert result.transactions[0].account_id == chase


def test_monarch_importer_accepts_a_byte_order_mark() -> None:
    result = MonarchCsvImporter().parse(
        b"\xef\xbb\xbf" + CSV.encode(), _context(uuid.uuid4())
    )

    assert len(result.transactions) == 3


def test_monarch_importer_rejects_non_utf8() -> None:
    with pytest.raises(ValidationError, match="not valid UTF-8"):
        MonarchCsvImporter().parse(b"\xff\xfe\x00bad", _context(uuid.uuid4()))
