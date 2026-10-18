"""US-HOUSE-11: a contribution that passed through no imported account is
recorded as an excluded row of a hand-entered joint account."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
import uuid

import attrs
import pytest

from src.application.use_cases.record_manual_transaction import (
    RecordManualTransactionCommand,
    RecordManualTransactionUseCase,
)
from src.domain.constants import HOUSE_CONTRIBUTION_CATEGORY
from src.domain.entities.account import (
    Account,
    joint_account_id,
    personal_account_id,
)
from src.domain.entities.category import Category
from src.domain.entities.transaction import Transaction
from src.domain.entities.upload import MANUAL_IMPORTER, manual_upload_id
from src.domain.exceptions import PeriodFinalizedError, ValidationError
from tests.fixtures.factories import (
    ALICE,
    BOB,
    make_account,
    make_category_group,
    make_joint_account,
    make_manual_transaction,
    make_reconciliation_period,
    make_transfer_group,
    make_upload,
)
from tests.fixtures.mocks import make_mock_uow

ESCROW_ID = joint_account_id("Escrow")
BASE = RecordManualTransactionCommand(
    account_name="Escrow",
    date=date(2025, 6, 30),
    amount=Decimal("12000.00"),
    description="Closing costs",
    share_kind="closing",
    owner_shares={ALICE.id: 70, BOB.id: 30},
    entered_by_person_id=BOB.id,
    document_ref="Closing statement p. 2",
)


def _uow(existing: list[Transaction] | None = None) -> AsyncMock:
    uow = make_mock_uow()
    uow.persons.get_all.return_value = [ALICE, BOB]
    uow.categories.get_by_name.return_value = None
    uow.transactions.get_by_date_range.return_value = existing or []
    return uow


def _with_escrow(uow: AsyncMock) -> None:
    """The hand-entered Escrow account and its manual upload exist."""
    uow.accounts.get_by_ids.return_value = [make_joint_account("Escrow")]
    uow.uploads.get_by_ids.return_value = [
        make_upload(
            id=manual_upload_id(ESCROW_ID), person_id=BOB.id, importer=MANUAL_IMPORTER
        )
    ]


async def _record(uow: AsyncMock, **overrides: object) -> Transaction:
    command = attrs.evolve(BASE, **overrides)
    result = await RecordManualTransactionUseCase().execute(command, uow)
    return result.transaction


class TestRecordManualTransaction:
    async def test_the_row_is_an_excluded_joint_row_tagged_with_its_kind(
        self,
    ) -> None:
        uow = _uow()

        row = await _record(uow)

        assert (row.account, row.account_id) == ("Escrow", ESCROW_ID)
        assert row.upload_id == manual_upload_id(ESCROW_ID)
        assert (row.date, row.amount) == (date(2025, 6, 30), Decimal("-12000.00"))
        assert row.payer_person_id is None
        assert row.payer_percentage == 100
        assert row.owner_shares == {ALICE.id: 70, BOB.id: 30}
        assert (row.household, row.is_excluded, row.is_settlement) == (
            False,
            True,
            False,
        )
        assert row.tags == ("share:closing",)
        assert (row.merchant, row.original_statement, row.notes) == (
            "Closing costs",
            "Closing costs",
            "Closing statement p. 2",
        )
        assert (row.category, row.occurrence) == (HOUSE_CONTRIBUTION_CATEGORY, 0)
        uow.transactions.save_batch.assert_awaited_once_with([row])
        uow.commit.assert_awaited_once()

    async def test_the_first_entry_adds_the_account_upload_and_category(
        self,
    ) -> None:
        uow = _uow()

        await _record(uow)

        uow.accounts.get_by_ids.assert_awaited_once_with([
            ESCROW_ID,
            personal_account_id(ALICE.id, "Escrow"),
            personal_account_id(BOB.id, "Escrow"),
        ])
        uow.accounts.add_missing.assert_awaited_once_with([
            make_joint_account("Escrow")
        ])
        [upload] = uow.uploads.save.await_args.args
        assert upload.id == manual_upload_id(ESCROW_ID)
        assert (upload.person_id, upload.importer, upload.content_sha256) == (
            BOB.id,
            MANUAL_IMPORTER,
            None,
        )
        [category] = uow.categories.save.await_args.args
        assert (category.name, category.group_id) == (
            HOUSE_CONTRIBUTION_CATEGORY,
            None,
        )

    async def test_the_category_maps_to_the_transfer_group_when_one_exists(
        self,
    ) -> None:
        """Money moved into the home is no spending, and Settings has no
        unmapped category to raise."""
        uow = _uow()
        transfer, _ = make_transfer_group()
        uow.category_groups.get_all.return_value = [make_category_group(), transfer]

        await _record(uow)

        [category] = uow.categories.save.await_args.args
        assert category.group_id == transfer.id

    async def test_a_later_entry_reuses_the_account_upload_and_category(
        self,
    ) -> None:
        uow = _uow()
        _with_escrow(uow)
        uow.categories.get_by_name.return_value = Category(
            id=ESCROW_ID, name=HOUSE_CONTRIBUTION_CATEGORY, group_id=None
        )

        row = await _record(uow, entered_by_person_id=ALICE.id)

        assert row.upload_id == manual_upload_id(ESCROW_ID)
        uow.accounts.add_missing.assert_not_called()
        uow.uploads.save.assert_not_called()
        uow.categories.save.assert_not_called()

    async def test_the_occurrence_never_collides_with_a_twin(self) -> None:
        """A twin of the same date, amount, and statement takes the next free
        occurrence, even after a deletion leaves a gap. The read is by the
        rows' current date, and other accounts' rows do not count."""
        twin = attrs.evolve(
            make_manual_transaction(amount=Decimal("-12000.00"), account="Escrow"),
            date=BASE.date,
            original_statement=BASE.description,
            occurrence=1,
        )
        other_statement = attrs.evolve(
            twin, original_statement="Title fee", occurrence=4
        )
        other_account = attrs.evolve(
            twin, account_id=joint_account_id("Other"), occurrence=7
        )
        uow = _uow([twin, other_statement, other_account])

        row = await _record(uow)

        assert row.occurrence == 2
        uow.transactions.get_by_date_range.assert_awaited_once_with(
            BASE.date, BASE.date, tags=None
        )

    async def test_owner_shares_must_name_the_couple(self) -> None:
        uow = _uow()

        stranger = uuid.uuid4()

        with pytest.raises(ValidationError, match="couple"):
            await _record(uow, owner_shares={ALICE.id: 50, stranger: 50})
        uow.transactions.save_batch.assert_not_called()

    async def test_a_finalized_month_is_refused(self) -> None:
        uow = _uow()
        uow.reconciliation_periods.get_by_period.return_value = (
            make_reconciliation_period(year=2025, month=6, is_finalized=True)
        )

        with pytest.raises(PeriodFinalizedError):
            await _record(uow)
        uow.transactions.save_batch.assert_not_called()

    @pytest.mark.parametrize(
        "imported",
        [
            make_account(name="Escrow", owner_person_id=ALICE.id),
            make_joint_account("Escrow"),
        ],
        ids=["personal", "joint"],
    )
    async def test_an_imported_accounts_label_is_refused(
        self, imported: Account
    ) -> None:
        """A joint account without a manual upload came from an import."""
        uow = _uow()
        uow.accounts.get_by_ids.return_value = [imported]

        with pytest.raises(ValidationError, match="imported account"):
            await _record(uow)
        uow.accounts.add_missing.assert_not_called()
        uow.transactions.save_batch.assert_not_called()

    @pytest.mark.parametrize("amount", [Decimal(0), Decimal("-5.00")])
    def test_the_amount_must_be_positive(self, amount: Decimal) -> None:
        with pytest.raises(ValueError, match="amount"):
            attrs.evolve(BASE, amount=amount)

    def test_the_amount_is_kept_in_cents(self) -> None:
        assert attrs.evolve(BASE, amount=Decimal("10.005")).amount == Decimal("10.01")
