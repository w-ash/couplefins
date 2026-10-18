"""US-ACCOUNT-1: unmarking returns a joint account's rows to the partners
who imported them."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.unmark_account_joint import (
    UnmarkAccountJointCommand,
    UnmarkAccountJointResult,
    UnmarkAccountJointUseCase,
)
from src.domain.entities.account import joint_account_id, personal_account_id
from src.domain.entities.transaction import Transaction
from src.domain.entities.upload import MANUAL_IMPORTER, manual_upload_id
from src.domain.exceptions import NotFoundError, PeriodFinalizedError, ValidationError
from tests.fixtures.factories import (
    ALICE,
    BOB,
    make_joint_account,
    make_manual_transaction,
    make_reconciliation_period,
    make_transaction,
    make_upload,
)
from tests.fixtures.mocks import make_mock_uow

LABEL = "Joint Checking"
ALICE_UPLOAD = make_upload(person_id=ALICE.id)
BOB_UPLOAD = make_upload(person_id=BOB.id)


def _uow(rows: list[Transaction]) -> AsyncMock:
    uow = make_mock_uow()
    uow.accounts.get_by_ids.return_value = [make_joint_account(LABEL)]
    uow.transactions.get_by_account_ids.return_value = rows
    uow.uploads.get_by_ids.return_value = [ALICE_UPLOAD, BOB_UPLOAD]
    return uow


async def _unmark(uow: AsyncMock) -> UnmarkAccountJointResult:
    return await UnmarkAccountJointUseCase().execute(
        UnmarkAccountJointCommand(LABEL), uow
    )


async def test_rows_return_to_their_uploader() -> None:
    alices = make_transaction(joint=True, account=LABEL, upload_id=ALICE_UPLOAD.id)
    bobs = make_transaction(
        joint=True,
        account=LABEL,
        upload_id=BOB_UPLOAD.id,
        owner_shares={ALICE.id: 40, BOB.id: 60},
        depositor_person_id=BOB.id,
    )
    uow = _uow([alices, bobs])

    result = await _unmark(uow)

    (rows,) = uow.transactions.rekey_batch.call_args.args
    by_id = {tx.id: tx for tx in rows}
    alice_row, bob_row = by_id[alices.id], by_id[bobs.id]
    assert (alice_row.payer_person_id, alice_row.account_id) == (
        ALICE.id,
        personal_account_id(ALICE.id, LABEL),
    )
    assert (bob_row.payer_person_id, bob_row.account_id) == (
        BOB.id,
        personal_account_id(BOB.id, LABEL),
    )
    # Owner shares carry back into the uploader's split; no shares is unsplit.
    assert (alice_row.payer_percentage, bob_row.payer_percentage) == (100, 60)
    assert all(tx.household for tx in rows)
    assert all(tx.owner_shares is None for tx in rows)
    assert all(tx.depositor_person_id is None for tx in rows)
    (accounts,) = uow.accounts.add_missing.call_args.args
    assert {(a.id, a.owner_person_id) for a in accounts} == {
        (personal_account_id(ALICE.id, LABEL), ALICE.id),
        (personal_account_id(BOB.id, LABEL), BOB.id),
    }
    uow.accounts.delete_by_ids.assert_awaited_once_with([joint_account_id(LABEL)])
    uow.commit.assert_awaited_once()
    assert result.moved_count == 2


async def test_refuses_when_an_affected_month_is_finalized() -> None:
    uow = _uow([make_transaction(joint=True, account=LABEL, upload_id=BOB_UPLOAD.id)])
    uow.reconciliation_periods.get_by_periods.return_value = [
        make_reconciliation_period(
            year=2026, month=1, is_finalized=True, finalized_at=datetime.now(UTC)
        )
    ]

    with pytest.raises(PeriodFinalizedError):
        await _unmark(uow)

    uow.transactions.rekey_batch.assert_not_called()
    uow.commit.assert_not_called()


async def test_a_label_that_is_not_joint_is_not_found() -> None:
    uow = _uow([])
    uow.accounts.get_by_ids.return_value = []

    with pytest.raises(NotFoundError, match=LABEL):
        await _unmark(uow)

    uow.transactions.rekey_batch.assert_not_called()


async def test_a_hand_entered_account_is_refused() -> None:
    """Its rows were imported by no one, so no partner can take them back."""
    joint = make_joint_account(LABEL)
    uow = _uow([make_manual_transaction(account=LABEL)])
    uow.uploads.get_by_ids.return_value = [
        make_upload(
            id=manual_upload_id(joint.id), person_id=BOB.id, importer=MANUAL_IMPORTER
        )
    ]

    with pytest.raises(ValidationError, match="hand-entered"):
        await _unmark(uow)

    uow.transactions.rekey_batch.assert_not_called()
    uow.accounts.delete_by_ids.assert_not_called()
