from datetime import date

import attrs

from src.application.use_cases.list_manual_transactions import (
    ListManualTransactionsCommand,
    ListManualTransactionsUseCase,
)
from src.domain.entities.upload import MANUAL_IMPORTER, manual_upload_id
from tests.fixtures.factories import (
    ALICE,
    make_account,
    make_joint_account,
    make_manual_transaction,
    make_upload,
)
from tests.fixtures.mocks import make_mock_uow


async def test_lists_the_hand_entered_accounts_rows_newest_first() -> None:
    escrow, checking = make_joint_account("Escrow"), make_joint_account("Checking")
    older, newer = (
        attrs.evolve(make_manual_transaction(), date=day)
        for day in (date(2025, 6, 30), date(2026, 2, 1))
    )
    uow = make_mock_uow()
    uow.accounts.get_all.return_value = [
        escrow,
        checking,
        make_account(owner_person_id=ALICE.id),
    ]
    uow.uploads.get_by_ids.return_value = [
        make_upload(
            id=manual_upload_id(escrow.id), person_id=ALICE.id, importer=MANUAL_IMPORTER
        )
    ]
    uow.transactions.get_by_account_ids.return_value = [older, newer]

    result = await ListManualTransactionsUseCase().execute(
        ListManualTransactionsCommand(), uow
    )

    assert result.transactions == [newer, older]
    uow.uploads.get_by_ids.assert_awaited_once_with([
        manual_upload_id(escrow.id),
        manual_upload_id(checking.id),
    ])
    uow.transactions.get_by_account_ids.assert_awaited_once_with([escrow.id])


async def test_no_joint_account_reads_no_uploads() -> None:
    uow = make_mock_uow()
    uow.accounts.get_all.return_value = [make_account(owner_person_id=ALICE.id)]

    result = await ListManualTransactionsUseCase().execute(
        ListManualTransactionsCommand(), uow
    )

    assert result.transactions == []
    uow.uploads.get_by_ids.assert_not_called()
