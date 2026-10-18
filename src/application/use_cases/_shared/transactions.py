from collections.abc import Iterable, Sequence
from uuid import UUID

from src.application.use_cases._shared.finalization import (
    assert_periods_not_finalized,
    months_of,
)
from src.application.use_cases._shared.transaction_reads import fetch_account_rows
from src.domain.dedup import (
    ClassifiedTransaction,
    classify_transactions,
    find_removed_transactions,
)
from src.domain.entities.account import Account
from src.domain.entities.category import Category
from src.domain.entities.transaction import Transaction
from src.domain.entities.upload import Upload, manual_upload_id
from src.domain.exceptions import NotFoundError
from src.domain.filters import is_joint_row, payer_of
from src.domain.parsing.importer import ImportContext, Importer, ParseResult
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


def joint_accounts(accounts: Iterable[Account]) -> list[Account]:
    """The joint accounts among `accounts`."""
    return [a for a in accounts if a.kind == "joint"]


async def manual_accounts(
    uow: UnitOfWorkProtocol, accounts: Iterable[Account]
) -> list[Account]:
    """The hand-entered accounts among `accounts`, in their order: the joint
    accounts whose manual upload exists. One read of the uploads, and none
    when `accounts` holds no joint account."""
    joint = joint_accounts(accounts)
    if not joint:
        return []
    uploads = await uow.uploads.get_by_ids([manual_upload_id(a.id) for a in joint])
    manual = {u.id for u in uploads if u.is_manual}
    return [a for a in joint if manual_upload_id(a.id) in manual]


async def parse_file(
    uow: UnitOfWorkProtocol,
    importer: Importer,
    data: bytes,
    *,
    person_id: UUID,
    upload_id: UUID,
    accounts: Sequence[Account],
) -> ParseResult:
    """Parse a file into transactions for the uploader.

    Rows on a label marked joint import into that joint account. A
    hand-entered account is no import target: rows on its name import into
    the uploader's personal account of that name. `accounts` is every
    account, read once per upload.
    """
    hand_entered = {a.id for a in await manual_accounts(uow, accounts)}
    ctx = ImportContext(
        payer_person_id=person_id,
        upload_id=upload_id,
        persons=tuple(await uow.persons.get_all()),
        joint_labels=frozenset(
            a.name for a in joint_accounts(accounts) if a.id not in hand_entered
        ),
    )
    return importer.parse(data, ctx)


async def delete_transactions_with_links(
    uow: UnitOfWorkProtocol, transactions: list[Transaction]
) -> list[str]:
    """Delete rows with their edit history and settlement links.

    Return one warning for each row that was linked to a settlement. The link
    is removed; the settlement record stays.
    """
    if not transactions:
        return []
    ids = [tx.id for tx in transactions]
    warnings: list[str] = []
    links = await uow.settlement_transaction_links.get_by_transaction_ids(ids)
    if links:
        linked_ids = {link.transaction_id for link in links}
        warnings = [
            f"Removed transaction {tx.merchant} ({tx.date.isoformat()}) "
            "was linked to a settlement — the link was removed"
            for tx in transactions
            if tx.id in linked_ids
        ]
        await uow.settlement_transaction_links.delete_by_transaction_ids(ids)
    await uow.transaction_edits.delete_by_transaction_ids(ids)
    await uow.transactions.delete_by_ids(ids)
    return warnings


def find_new_categories(
    categories: list[Category], tx_categories: set[str]
) -> list[str]:
    """Categories with no row in the categories table at all."""
    known = {c.name for c in categories}
    return sorted(tx_categories - known)


def find_unmapped_categories(
    categories: list[Category], tx_categories: set[str]
) -> list[str]:
    """Categories that exist in DB but have group_id=None."""
    unmapped = {c.name for c in categories if c.group_id is None}
    return sorted(tx_categories & unmapped)


def find_all_unmapped_categories(
    categories: list[Category], tx_categories: set[str]
) -> list[str]:
    """Categories that are either unknown or known-but-unmapped (group_id=None).

    Single pass over categories to avoid redundant iteration.
    """
    known: set[str] = set()
    mapped: set[str] = set()
    for c in categories:
        known.add(c.name)
        if c.group_id is not None:
            mapped.add(c.name)
    return sorted(tx_categories - mapped)


async def classify_against_existing(
    incoming: list[Transaction],
    person_id: UUID,
    accounts: Sequence[Account],
    uow: UnitOfWorkProtocol,
) -> tuple[list[ClassifiedTransaction], list[Transaction], list[Transaction]]:
    """Fetch existing transactions for the incoming date range and classify.

    The fetch matches on original_date-or-date so rows whose date was edited
    in-app past the CSV window boundary still pair with their CSV twins
    (natural_key uses the same original-* fallback).

    The fetch covers the uploader's personal accounts (from `accounts`) plus
    every account the file names, which adds the joint accounts it names.

    Returns (classified, existing, removed):
    - existing is needed by preview to show diffs
    - removed are the rows the uploader owns in that scope and window that
      the new CSV no longer contains (re-upload is a true replace). A joint
      row is the uploader's when their own upload imported it, so a
      partner's file never removes it.
    """
    if not incoming:
        return [], [], []
    dates = [tx.date for tx in incoming]
    account_ids = {a.id for a in accounts if a.owner_person_id == person_id} | {
        tx.account_id for tx in incoming
    }
    existing = await uow.transactions.get_by_account_ids_and_original_date_range(
        sorted(account_ids), min(dates), max(dates)
    )
    owned = await _owned_by(uow, existing, person_id)
    return (
        classify_transactions(incoming, existing),
        existing,
        find_removed_transactions(incoming, owned),
    )


async def _owned_by(
    uow: UnitOfWorkProtocol, rows: list[Transaction], person_id: UUID
) -> list[Transaction]:
    """The rows a person owns: their personal rows, and the joint rows their
    own uploads imported. A hand-entered row is no import, so a re-import
    never owns it and never removes it."""
    uploads = await load_uploads(uow, [tx for tx in rows if is_joint_row(tx)])

    def owner(tx: Transaction) -> UUID | None:
        if not is_joint_row(tx):
            return payer_of(tx)
        upload = uploads[tx.upload_id]
        return None if upload.is_manual else upload.person_id

    return [tx for tx in rows if owner(tx) == person_id]


async def load_uploads(
    uow: UnitOfWorkProtocol, transactions: list[Transaction]
) -> dict[UUID, Upload]:
    """The upload that imported each row, by upload id."""
    upload_ids = sorted({tx.upload_id for tx in transactions}, key=str)
    if not upload_ids:
        return {}
    uploads = {u.id: u for u in await uow.uploads.get_by_ids(upload_ids)}
    missing = [i for i in upload_ids if i not in uploads]
    if missing:
        raise NotFoundError(f"Upload {missing[0]} not found")
    return uploads


async def load_rows_to_move(
    uow: UnitOfWorkProtocol, account_ids: list[UUID]
) -> tuple[list[Transaction], dict[UUID, Upload]]:
    """Every row in the accounts, and the upload that imported each.

    Moving a row between accounts edits it, so raise PeriodFinalizedError
    when any row's month is finalized.
    """
    rows = await fetch_account_rows(uow, account_ids)
    await assert_periods_not_finalized(uow, months_of(rows))
    return rows, await load_uploads(uow, rows)
