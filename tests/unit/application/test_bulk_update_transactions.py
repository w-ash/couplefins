from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
import uuid

import attrs
import pytest

from src.application.use_cases.bulk_update_transactions import (
    BulkUpdateTransactionsCommand,
    BulkUpdateTransactionsUseCase,
)
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import NotFoundError, PeriodFinalizedError, ValidationError
from tests.fixtures.factories import (
    ALICE,
    BOB,
    make_reconciliation_period,
    make_transaction,
)
from tests.fixtures.mocks import make_mock_uow


def _make_command(
    transaction_ids: list[uuid.UUID] | None = None,
    **kwargs: object,
) -> BulkUpdateTransactionsCommand:
    return BulkUpdateTransactionsCommand(
        transaction_ids=transaction_ids
        if transaction_ids is not None
        else [uuid.uuid4()],
        **kwargs,  # type: ignore[arg-type]
    )


# --- Bulk category/payer_percentage (multi-item) ---


async def test_updates_category_for_multiple_transactions() -> None:
    uow = make_mock_uow()
    tx1 = make_transaction(category="Dining Out")
    tx2 = make_transaction(category="Dining Out")
    uow.transactions.get_by_ids.return_value = [tx1, tx2]

    command = _make_command(transaction_ids=[tx1.id, tx2.id], category="Fast Food")
    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert result.updated_count == 2
    assert uow.transactions.update_mutable_fields.call_count == 2
    for call in uow.transactions.update_mutable_fields.call_args_list:
        assert call[0][0].category == "Fast Food"
    uow.transaction_edits.save_batch.assert_called_once()
    edits = uow.transaction_edits.save_batch.call_args[0][0]
    assert len(edits) == 2
    assert all(e.field_name == "category" for e in edits)
    uow.commit.assert_called_once()


async def test_updates_payer_percentage_for_multiple_transactions() -> None:
    uow = make_mock_uow()
    tx1 = make_transaction(payer_percentage=50)
    tx2 = make_transaction(payer_percentage=60)
    uow.transactions.get_by_ids.return_value = [tx1, tx2]

    command = _make_command(transaction_ids=[tx1.id, tx2.id], payer_percentage=70)
    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert result.updated_count == 2
    for call in uow.transactions.update_mutable_fields.call_args_list:
        assert call[0][0].payer_percentage == 70


async def test_updates_both_category_and_payer_percentage() -> None:
    uow = make_mock_uow()
    tx = make_transaction(category="Dining Out", payer_percentage=50)
    uow.transactions.get_by_ids.return_value = [tx]

    command = _make_command(
        transaction_ids=[tx.id], category="Fast Food", payer_percentage=70
    )
    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert result.updated_count == 1
    updated = uow.transactions.update_mutable_fields.call_args[0][0]
    assert updated.category == "Fast Food"
    assert updated.payer_percentage == 70
    edits = uow.transaction_edits.save_batch.call_args[0][0]
    assert len(edits) == 2
    field_names = {e.field_name for e in edits}
    assert field_names == {"category", "payer_percentage"}


async def test_skips_unchanged_transactions() -> None:
    uow = make_mock_uow()
    tx = make_transaction(category="Dining Out")
    uow.transactions.get_by_ids.return_value = [tx]

    command = _make_command(transaction_ids=[tx.id], category="Dining Out")
    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert result.updated_count == 0
    uow.transactions.update_mutable_fields.assert_not_called()
    uow.transaction_edits.save_batch.assert_not_called()
    uow.commit.assert_called_once()


async def test_rejects_empty_transaction_ids() -> None:
    uow = make_mock_uow()
    command = _make_command(transaction_ids=[])

    with pytest.raises(ValidationError, match="At least one transaction ID"):
        await BulkUpdateTransactionsUseCase().execute(command, uow)


async def test_rejects_no_fields_to_update() -> None:
    uow = make_mock_uow()
    command = _make_command(transaction_ids=[uuid.uuid4()])

    with pytest.raises(ValidationError, match="At least one field"):
        await BulkUpdateTransactionsUseCase().execute(command, uow)


async def test_rejects_invalid_payer_percentage() -> None:
    uow = make_mock_uow()
    command = _make_command(transaction_ids=[uuid.uuid4()], payer_percentage=150)

    with pytest.raises(ValidationError, match="payer_percentage"):
        await BulkUpdateTransactionsUseCase().execute(command, uow)


async def test_raises_not_found_for_missing_transaction() -> None:
    uow = make_mock_uow()
    uow.transactions.get_by_ids.return_value = []
    missing_id = uuid.uuid4()
    command = _make_command(transaction_ids=[missing_id], category="Fast Food")

    with pytest.raises(NotFoundError, match=str(missing_id)):
        await BulkUpdateTransactionsUseCase().execute(command, uow)


async def test_rejects_update_to_finalized_period() -> None:
    uow = make_mock_uow()
    tx = make_transaction()
    uow.transactions.get_by_ids.return_value = [tx]
    uow.reconciliation_periods.get_by_periods.return_value = [
        make_reconciliation_period(
            year=tx.date.year,
            month=tx.date.month,
            is_finalized=True,
            finalized_at=datetime.now(UTC),
        )
    ]
    command = _make_command(transaction_ids=[tx.id], category="Fast Food")

    with pytest.raises(PeriodFinalizedError):
        await BulkUpdateTransactionsUseCase().execute(command, uow)


async def test_preserves_other_fields() -> None:
    uow = make_mock_uow()
    tx = make_transaction(
        merchant="Test Merchant",
        category="Dining Out",
        tags=("shared", "s50"),
        payer_percentage=50,
    )
    uow.transactions.get_by_ids.return_value = [tx]
    command = _make_command(transaction_ids=[tx.id], category="Fast Food")

    await BulkUpdateTransactionsUseCase().execute(command, uow)

    updated = uow.transactions.update_mutable_fields.call_args[0][0]
    assert updated.merchant == "Test Merchant"
    assert updated.tags == ("shared", "s50")
    assert updated.payer_percentage == 50
    assert updated.category == "Fast Food"


async def test_creates_correct_audit_edits() -> None:
    uow = make_mock_uow()
    tx = make_transaction(category="Dining Out", payer_percentage=50)
    uow.transactions.get_by_ids.return_value = [tx]
    command = _make_command(
        transaction_ids=[tx.id], category="Fast Food", payer_percentage=70
    )

    await BulkUpdateTransactionsUseCase().execute(command, uow)

    edits = uow.transaction_edits.save_batch.call_args[0][0]
    cat_edit = next(e for e in edits if e.field_name == "category")
    assert cat_edit.old_value == "Dining Out"
    assert cat_edit.new_value == "Fast Food"
    assert cat_edit.transaction_id == tx.id

    pct_edit = next(e for e in edits if e.field_name == "payer_percentage")
    assert pct_edit.old_value == "50"
    assert pct_edit.new_value == "70"


# --- Single-item (date/amount support, migrated from update_transaction) ---


async def test_single_field_update_creates_one_edit() -> None:
    uow = make_mock_uow()
    tx = make_transaction(category="Dining Out")
    uow.transactions.get_by_ids.return_value = [tx]
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[tx.id],
        category="Fast Food",
    )

    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert len(result.edits) == 1
    assert result.edits[0].field_name == "category"
    assert result.edits[0].old_value == "Dining Out"
    assert result.edits[0].new_value == "Fast Food"
    assert result.updated_transactions[0].category == "Fast Food"
    uow.transaction_edits.save_batch.assert_called_once()
    uow.commit.assert_called_once()


async def test_multi_field_update_creates_multiple_edits() -> None:
    uow = make_mock_uow()
    tx = make_transaction(category="Dining Out", tags=("shared",))
    uow.transactions.get_by_ids.return_value = [tx]
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[tx.id],
        category="Fast Food",
        tags=("shared", "s70"),
    )

    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert len(result.edits) == 2
    field_names = {e.field_name for e in result.edits}
    assert field_names == {"category", "tags"}


async def test_noop_when_values_unchanged() -> None:
    uow = make_mock_uow()
    tx = make_transaction(category="Dining Out")
    uow.transactions.get_by_ids.return_value = [tx]
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[tx.id],
        category="Dining Out",
    )

    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert len(result.edits) == 0
    uow.transaction_edits.save_batch.assert_not_called()
    uow.transactions.update_all_fields.assert_not_called()
    uow.transactions.update_mutable_fields.assert_not_called()
    uow.commit.assert_called_once()


async def test_finalization_guard_on_new_period_when_date_changes() -> None:
    uow = make_mock_uow()
    tx = make_transaction(date=date(2026, 1, 15))
    uow.transactions.get_by_ids.return_value = [tx]
    new_date = date(2026, 3, 10)

    def fake_get_by_period(year: int, month: int):
        if year == 2026 and month == 3:
            return make_reconciliation_period(
                year=2026, month=3, is_finalized=True, finalized_at=datetime.now(UTC)
            )
        return None

    uow.reconciliation_periods.get_by_period.side_effect = fake_get_by_period
    command = BulkUpdateTransactionsCommand(transaction_ids=[tx.id], date=new_date)

    with pytest.raises(PeriodFinalizedError):
        await BulkUpdateTransactionsUseCase().execute(command, uow)


async def test_original_date_set_on_first_date_edit() -> None:
    uow = make_mock_uow()
    original_date = date(2026, 1, 15)
    tx = make_transaction(date=original_date)
    uow.transactions.get_by_ids.return_value = [tx]
    new_date = date(2026, 1, 20)
    command = BulkUpdateTransactionsCommand(transaction_ids=[tx.id], date=new_date)

    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert result.updated_transactions[0].date == new_date
    assert result.updated_transactions[0].original_date == original_date


async def test_original_date_preserved_on_subsequent_edit() -> None:
    uow = make_mock_uow()
    first_original = date(2026, 1, 10)
    tx = make_transaction(date=date(2026, 1, 20), original_date=first_original)
    uow.transactions.get_by_ids.return_value = [tx]
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[tx.id], date=date(2026, 1, 25)
    )

    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert result.updated_transactions[0].original_date == first_original


async def test_original_amount_set_on_first_amount_edit() -> None:
    uow = make_mock_uow()
    original_amount = Decimal("-50.00")
    tx = make_transaction(amount=original_amount)
    uow.transactions.get_by_ids.return_value = [tx]
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[tx.id], amount=Decimal("-75.00")
    )

    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert result.updated_transactions[0].amount == Decimal("-75.00")
    assert result.updated_transactions[0].original_amount == original_amount


async def test_original_amount_preserved_on_subsequent_edit() -> None:
    uow = make_mock_uow()
    first_original = Decimal("-42.00")
    tx = make_transaction(amount=Decimal("-60.00"), original_amount=first_original)
    uow.transactions.get_by_ids.return_value = [tx]
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[tx.id], amount=Decimal("-99.00")
    )

    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert result.updated_transactions[0].original_amount == first_original


async def test_date_change_uses_update_all_fields() -> None:
    uow = make_mock_uow()
    tx = make_transaction(date=date(2026, 1, 15))
    uow.transactions.get_by_ids.return_value = [tx]
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[tx.id], date=date(2026, 1, 20)
    )

    await BulkUpdateTransactionsUseCase().execute(command, uow)

    uow.transactions.update_all_fields.assert_called_once()
    uow.transactions.update_mutable_fields.assert_not_called()


async def test_category_change_uses_update_mutable_fields() -> None:
    uow = make_mock_uow()
    tx = make_transaction(category="Dining Out")
    uow.transactions.get_by_ids.return_value = [tx]
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[tx.id], category="Fast Food"
    )

    await BulkUpdateTransactionsUseCase().execute(command, uow)

    uow.transactions.update_mutable_fields.assert_called_once()
    uow.transactions.update_all_fields.assert_not_called()


async def test_payer_percentage_update() -> None:
    uow = make_mock_uow()
    tx = make_transaction(payer_percentage=50)
    uow.transactions.get_by_ids.return_value = [tx]
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[tx.id], payer_percentage=70
    )

    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert result.updated_transactions[0].payer_percentage == 70
    assert len(result.edits) == 1
    assert result.edits[0].field_name == "payer_percentage"


async def test_payer_percentage_sentinel_means_no_change() -> None:
    uow = make_mock_uow()
    tx = make_transaction(payer_percentage=50, category="Dining Out")
    uow.transactions.get_by_ids.return_value = [tx]
    # payer_percentage defaults to _UNSET, so it won't be in updates
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[tx.id], category="Fast Food"
    )

    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert result.updated_transactions[0].payer_percentage == 50
    assert all(e.field_name != "payer_percentage" for e in result.edits)


async def test_preserves_single_item_other_fields() -> None:
    uow = make_mock_uow()
    tx = make_transaction(
        merchant="Original Merchant",
        category="Dining Out",
        notes="Test notes",
        tags=("shared", "s50"),
        payer_percentage=50,
    )
    uow.transactions.get_by_ids.return_value = [tx]
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[tx.id], category="Fast Food"
    )

    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    updated = result.updated_transactions[0]
    assert updated.merchant == "Original Merchant"
    assert updated.notes == "Test notes"
    assert updated.tags == ("shared", "s50")
    assert updated.payer_percentage == 50
    assert updated.category == "Fast Food"


# --- Multi-item guards for date/amount ---


async def test_rejects_date_for_multi_item() -> None:
    uow = make_mock_uow()
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[uuid.uuid4(), uuid.uuid4()],
        date=date(2026, 2, 1),
    )

    with pytest.raises(ValidationError, match="single transaction"):
        await BulkUpdateTransactionsUseCase().execute(command, uow)


async def test_rejects_amount_for_multi_item() -> None:
    uow = make_mock_uow()
    command = BulkUpdateTransactionsCommand(
        transaction_ids=[uuid.uuid4(), uuid.uuid4()],
        amount=Decimal("-100.00"),
    )

    with pytest.raises(ValidationError, match="single transaction"):
        await BulkUpdateTransactionsUseCase().execute(command, uow)


async def test_result_includes_updated_transactions() -> None:
    uow = make_mock_uow()
    tx1 = make_transaction(category="Dining Out")
    tx2 = make_transaction(category="Dining Out")
    uow.transactions.get_by_ids.return_value = [tx1, tx2]

    command = _make_command(transaction_ids=[tx1.id, tx2.id], category="Fast Food")
    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert len(result.updated_transactions) == 2
    assert all(t.category == "Fast Food" for t in result.updated_transactions)


# --- Notes editing ---


async def test_updates_notes_for_single_transaction() -> None:
    uow = make_mock_uow()
    tx = make_transaction(notes="old note")
    uow.transactions.get_by_ids.return_value = [tx]
    command = BulkUpdateTransactionsCommand(transaction_ids=[tx.id], notes="new note")

    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert result.updated_count == 1
    updated = uow.transactions.update_mutable_fields.call_args[0][0]
    assert updated.notes == "new note"
    edits = uow.transaction_edits.save_batch.call_args[0][0]
    assert len(edits) == 1
    assert edits[0].field_name == "notes"
    assert edits[0].old_value == "old note"
    assert edits[0].new_value == "new note"


async def test_notes_no_edit_when_unchanged() -> None:
    uow = make_mock_uow()
    tx = make_transaction(notes="same note")
    uow.transactions.get_by_ids.return_value = [tx]
    command = BulkUpdateTransactionsCommand(transaction_ids=[tx.id], notes="same note")

    result = await BulkUpdateTransactionsUseCase().execute(command, uow)

    assert result.updated_count == 0
    uow.transactions.update_mutable_fields.assert_not_called()
    uow.transaction_edits.save_batch.assert_not_called()


# --- Edit attribution ---


async def test_edits_carry_edited_by_person_id() -> None:
    uow = make_mock_uow()
    tx = make_transaction(category="Dining Out")
    uow.transactions.get_by_ids.return_value = [tx]
    person_id = uuid.uuid4()
    command = _make_command(
        transaction_ids=[tx.id],
        category="Fast Food",
        edited_by_person_id=person_id,
    )

    await BulkUpdateTransactionsUseCase().execute(command, uow)

    edits = uow.transaction_edits.save_batch.call_args[0][0]
    assert all(e.edited_by_person_id == person_id for e in edits)


# --- Joint rows: owner shares and depositor (US-JOINT-1, US-JOINT-2) ---


def _joint_uow(*rows: Transaction) -> AsyncMock:
    uow = make_mock_uow()
    uow.persons.get_all.return_value = [ALICE, BOB]
    uow.transactions.get_by_ids.return_value = list(rows)
    return uow


async def _apply(uow: AsyncMock, command: BulkUpdateTransactionsCommand) -> None:
    await BulkUpdateTransactionsUseCase().execute(command, uow)


async def test_sets_owner_shares_and_depositor_on_a_joint_row() -> None:
    deposit = make_transaction(joint=True, amount=Decimal("1600.00"))
    uow = _joint_uow(deposit)

    await _apply(
        uow,
        BulkUpdateTransactionsCommand(
            transaction_ids=[deposit.id],
            owner_shares={ALICE.id: 60, BOB.id: 40},
            depositor_person_id=ALICE.id,
        ),
    )

    updated = uow.transactions.update_mutable_fields.call_args.args[0]
    assert updated.owner_shares == {ALICE.id: 60, BOB.id: 40}
    assert updated.depositor_person_id == ALICE.id
    edits = {
        e.field_name: e for e in uow.transaction_edits.save_batch.call_args.args[0]
    }
    assert not edits["owner_shares"].old_value
    assert edits["owner_shares"].new_value == f"{ALICE.id}:60,{BOB.id}:40"
    assert edits["depositor_person_id"].new_value == str(ALICE.id)


async def test_null_resets_owner_shares_and_unassigns_the_depositor() -> None:
    deposit = make_transaction(
        joint=True,
        amount=Decimal("1600.00"),
        owner_shares={ALICE.id: 60, BOB.id: 40},
        depositor_person_id=BOB.id,
    )
    uow = _joint_uow(deposit)

    await _apply(
        uow,
        BulkUpdateTransactionsCommand(
            transaction_ids=[deposit.id], owner_shares=None, depositor_person_id=None
        ),
    )

    updated = uow.transactions.update_mutable_fields.call_args.args[0]
    assert (updated.owner_shares, updated.depositor_person_id) == (None, None)


@pytest.mark.parametrize(
    "change",
    [
        {"owner_shares": {ALICE.id: 50, BOB.id: 50}},
        {"depositor_person_id": ALICE.id},
    ],
)
async def test_joint_only_fields_are_rejected_on_a_personal_row(
    change: dict[str, object],
) -> None:
    personal = make_transaction(payer_person_id=ALICE.id)
    uow = _joint_uow(personal)
    command = attrs.evolve(
        BulkUpdateTransactionsCommand(transaction_ids=[personal.id]), **change
    )

    with pytest.raises(ValidationError, match="joint-account"):
        await _apply(uow, command)

    uow.commit.assert_not_called()


async def test_a_payer_split_is_rejected_on_a_joint_row() -> None:
    joint = make_transaction(joint=True)
    uow = _joint_uow(joint)

    with pytest.raises(ValidationError, match="no payer split"):
        await _apply(
            uow,
            BulkUpdateTransactionsCommand(
                transaction_ids=[joint.id], payer_percentage=50
            ),
        )


async def test_a_joint_row_stays_household() -> None:
    joint = make_transaction(joint=True)
    uow = _joint_uow(joint)

    with pytest.raises(ValidationError, match="always household"):
        await _apply(
            uow,
            BulkUpdateTransactionsCommand(transaction_ids=[joint.id], household=False),
        )


@pytest.mark.parametrize(
    ("shares", "message"),
    [
        ({ALICE.id: 60, uuid.uuid4(): 40}, "each of the couple"),
        ({ALICE.id: 60, BOB.id: 30}, "sum to 100"),
    ],
)
async def test_owner_shares_must_split_the_couple_whole(
    shares: dict[uuid.UUID, int], message: str
) -> None:
    joint = make_transaction(joint=True)
    uow = _joint_uow(joint)

    with pytest.raises(ValidationError, match=message):
        await _apply(
            uow,
            BulkUpdateTransactionsCommand(
                transaction_ids=[joint.id], owner_shares=shares
            ),
        )


async def test_the_depositor_must_be_one_of_the_couple() -> None:
    joint = make_transaction(joint=True, amount=Decimal("100.00"))
    uow = _joint_uow(joint)

    with pytest.raises(ValidationError, match="not one of the couple"):
        await _apply(
            uow,
            BulkUpdateTransactionsCommand(
                transaction_ids=[joint.id], depositor_person_id=uuid.uuid4()
            ),
        )
