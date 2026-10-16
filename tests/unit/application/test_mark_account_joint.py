"""US-ACCOUNT-1: marking a label joint moves both partners' rows into one
joint account."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import attrs
import pytest

from src.application.use_cases.mark_account_joint import (
    MarkAccountJointCommand,
    MarkAccountJointResult,
    MarkAccountJointUseCase,
)
from src.domain.entities.account import joint_account_id, personal_account_id
from src.domain.entities.transaction import Transaction
from src.domain.entities.upload import Upload
from src.domain.exceptions import NotFoundError, PeriodFinalizedError, ValidationError
from src.domain.filters import is_joint_row
from tests.fixtures.factories import (
    ALICE,
    BOB,
    make_account,
    make_reconciliation_period,
    make_settlement_transaction_link,
    make_transaction,
    make_upload,
)
from tests.fixtures.mocks import make_mock_uow

LABEL = "Joint Checking"
JOINT_ID = joint_account_id(LABEL)
PERSONAL_IDS = [
    personal_account_id(ALICE.id, LABEL),
    personal_account_id(BOB.id, LABEL),
]
# Bob's upload is the older one.
ALICE_UPLOAD = make_upload(
    person_id=ALICE.id, uploaded_at=datetime(2026, 2, 3, tzinfo=UTC)
)
BOB_UPLOAD = make_upload(person_id=BOB.id, uploaded_at=datetime(2026, 2, 1, tzinfo=UTC))


def _row(
    upload: Upload,
    *,
    statement: str = "HARDWARE STORE",
    payer_percentage: int = 100,
    household: bool = False,
    on: date = date(2026, 1, 15),
    amount: str = "-120.00",
) -> Transaction:
    return make_transaction(
        payer_person_id=upload.person_id,
        upload_id=upload.id,
        account=LABEL,
        date=on,
        amount=Decimal(amount),
        original_statement=statement,
        payer_percentage=payer_percentage,
        household=household,
    )


def _uow(rows: list[Transaction]) -> AsyncMock:
    uow = make_mock_uow()
    uow.persons.get_all.return_value = [ALICE, BOB]
    uow.accounts.get_all.return_value = [
        make_account(id=PERSONAL_IDS[0], name=LABEL, owner_person_id=ALICE.id),
        make_account(id=PERSONAL_IDS[1], name=LABEL, owner_person_id=BOB.id),
    ]
    uow.transactions.get_by_account_ids.return_value = rows
    uow.uploads.get_by_ids.return_value = [ALICE_UPLOAD, BOB_UPLOAD]
    return uow


async def _mark(uow: AsyncMock) -> MarkAccountJointResult:
    return await MarkAccountJointUseCase().execute(MarkAccountJointCommand(LABEL), uow)


def _rekeyed(uow: AsyncMock) -> dict[str, Transaction]:
    (rows,) = uow.transactions.rekey_batch.call_args.args
    return {tx.original_statement: tx for tx in rows}


async def test_rows_lose_their_payer_and_leave_settlement() -> None:
    shared = _row(ALICE_UPLOAD, statement="SHARED", payer_percentage=70, household=True)
    spotted = _row(BOB_UPLOAD, statement="SPOTTED", payer_percentage=0)
    personal = _row(BOB_UPLOAD, statement="PERSONAL")
    uow = _uow([shared, spotted, personal])

    result = await _mark(uow)

    rows = _rekeyed(uow)
    assert all(is_joint_row(tx) for tx in rows.values())
    assert {tx.account_id for tx in rows.values()} == {JOINT_ID}
    assert {(tx.payer_percentage, tx.household) for tx in rows.values()} == {
        (100, True)
    }
    # A hand-set split carries into the owner shares; an unsplit row is 50/50.
    assert rows["SHARED"].owner_shares == {ALICE.id: 70, BOB.id: 30}
    assert rows["SPOTTED"].owner_shares == {BOB.id: 0, ALICE.id: 100}
    assert rows["PERSONAL"].owner_shares is None
    assert (result.moved_count, result.dropped_count) == (3, 0)
    uow.transactions.get_by_account_ids.assert_awaited_once_with(PERSONAL_IDS)
    (accounts,) = uow.accounts.add_missing.call_args.args
    assert [(a.id, a.kind, a.owner_person_id) for a in accounts] == [
        (JOINT_ID, "joint", None)
    ]
    uow.accounts.delete_by_ids.assert_awaited_once_with(PERSONAL_IDS)
    uow.commit.assert_awaited_once()


async def test_marking_names_a_deposits_depositor_and_ends_its_settlement_flag() -> (
    None
):
    """US-ACCOUNT-1: a marked row is the joint account's exactly as an imported
    one is (`as_joint_row`): money in names the one person its text names,
    and a row tagged `settlement` in Monarch leaves settlement."""
    deposit = _row(ALICE_UPLOAD, statement="TRANSFER FROM BOB", amount="1500.00")
    tagged = attrs.evolve(_row(BOB_UPLOAD, statement="VENMO"), is_settlement=True)
    uow = _uow([deposit, tagged])

    await _mark(uow)

    rows = _rekeyed(uow)
    assert rows["TRANSFER FROM BOB"].depositor_person_id == BOB.id
    assert rows["VENMO"].depositor_person_id is None
    assert not any(tx.is_settlement for tx in rows.values())


async def test_reads_the_uploads_once_for_every_row() -> None:
    uow = _uow([_row(ALICE_UPLOAD), _row(BOB_UPLOAD, statement="OTHER")])

    await _mark(uow)

    (upload_ids,) = uow.uploads.get_by_ids.call_args.args
    assert sorted(upload_ids, key=str) == sorted(
        [ALICE_UPLOAD.id, BOB_UPLOAD.id], key=str
    )
    uow.uploads.get_by_ids.assert_awaited_once()


async def test_twins_from_both_partners_collapse_to_the_older_upload() -> None:
    alices = _row(ALICE_UPLOAD)
    bobs = _row(BOB_UPLOAD)
    uow = _uow([alices, bobs])

    result = await _mark(uow)

    assert [tx.id for tx in _rekeyed(uow).values()] == [bobs.id]
    uow.transactions.delete_by_ids.assert_awaited_once_with([alices.id])
    uow.transaction_edits.delete_by_transaction_ids.assert_awaited_once_with([
        alices.id
    ])
    assert (result.moved_count, result.dropped_count) == (1, 1)


async def test_twins_are_dropped_before_the_survivor_moves() -> None:
    """The survivor takes the twin's natural key; the twin must be gone first."""
    uow = _uow([_row(ALICE_UPLOAD), _row(BOB_UPLOAD)])
    order: list[str] = []
    uow.transactions.delete_by_ids.side_effect = lambda _ids: order.append("delete")
    uow.transactions.rekey_batch.side_effect = lambda _rows: order.append("rekey")

    await _mark(uow)

    assert order == ["delete", "rekey"]


async def test_refuses_when_an_affected_month_is_finalized() -> None:
    uow = _uow([_row(ALICE_UPLOAD)])
    uow.reconciliation_periods.get_by_periods.return_value = [
        make_reconciliation_period(
            year=2026, month=1, is_finalized=True, finalized_at=datetime.now(UTC)
        )
    ]

    with pytest.raises(PeriodFinalizedError, match="2026-01"):
        await _mark(uow)

    uow.transactions.rekey_batch.assert_not_called()
    uow.commit.assert_not_called()


async def test_refuses_while_a_row_is_a_settlement_leg() -> None:
    leg = _row(ALICE_UPLOAD)
    uow = _uow([leg])
    uow.settlement_transaction_links.get_by_transaction_ids.return_value = [
        make_settlement_transaction_link(transaction_id=leg.id)
    ]

    with pytest.raises(ValidationError, match="settlement"):
        await _mark(uow)

    uow.transactions.rekey_batch.assert_not_called()


async def test_an_unknown_label_is_not_found() -> None:
    uow = _uow([])
    uow.accounts.get_all.return_value = []

    with pytest.raises(NotFoundError, match=LABEL):
        await _mark(uow)

    uow.accounts.add_missing.assert_not_called()
