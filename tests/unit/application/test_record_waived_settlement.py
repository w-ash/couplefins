from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.application.use_cases.record_waived_settlement import (
    RecordWaivedSettlementCommand,
    RecordWaivedSettlementUseCase,
)
from src.domain.entities.person import Person
from src.domain.exceptions import NotFoundError, ValidationError
from tests.fixtures.factories import (
    make_category,
    make_category_group,
    make_person,
    make_settlement,
    make_transaction,
    make_upload,
)
from tests.fixtures.mocks import make_mock_uow, set_passthrough_save


def _setup_uow(
    alice: Person,
    bob: Person,
    *,
    transactions: list | None = None,
    settlements: list | None = None,
    uploads_for: list[UUID] | None = None,
) -> AsyncMock:
    group = make_category_group()
    category = make_category(group_id=group.id)

    uow = make_mock_uow()
    uow.persons.get_by_ids.return_value = [alice, bob]
    uow.persons.get_all.return_value = [alice, bob]
    uow.transactions.get_household_by_date_range.return_value = transactions or []
    uow.categories.get_all.return_value = [category]
    uow.category_groups.get_all.return_value = [group]
    uow.settlements.get_by_period.return_value = settlements or []
    uow.settlement_transaction_links.get_by_settlement_ids.return_value = []
    uow.uploads.get_by_person_ids_with_transactions_in_date_range.return_value = [
        make_upload(person_id=pid) for pid in (uploads_for or [alice.id, bob.id])
    ]
    set_passthrough_save(uow)
    return uow


class TestRecordWaivedSettlement:
    async def test_waiver_persists_remaining_balance(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        # Alice paid $100 at 50/50 → Bob owes Alice $50.
        tx = make_transaction(
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        uow = _setup_uow(alice, bob, transactions=[tx])

        command = RecordWaivedSettlementCommand(
            year=2026,
            month=1,
            from_person_id=bob.id,
            to_person_id=alice.id,
            notes="Forgiven",
        )
        result = await RecordWaivedSettlementUseCase().execute(command, uow)

        assert result.settlement.amount == Decimal("50.00")
        assert result.settlement.is_waived is True
        assert result.settlement.method is None
        assert result.warnings == []
        uow.settlements.save.assert_called_once()

    async def test_waive_after_partial_payment_persists_remainder(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        # Bob already paid $30 of the $50 he owes.
        payment = make_settlement(
            year=2026,
            month=1,
            amount=Decimal("30.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
        )
        uow = _setup_uow(alice, bob, transactions=[tx], settlements=[payment])

        command = RecordWaivedSettlementCommand(
            year=2026,
            month=1,
            from_person_id=bob.id,
            to_person_id=alice.id,
        )
        result = await RecordWaivedSettlementUseCase().execute(command, uow)

        assert result.settlement.amount == Decimal("20.00")
        assert result.settlement.is_waived is True

    async def test_waive_zero_balance_raises(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = _setup_uow(alice, bob)

        command = RecordWaivedSettlementCommand(
            year=2026,
            month=1,
            from_person_id=bob.id,
            to_person_id=alice.id,
        )
        with pytest.raises(ValidationError, match="already settled"):
            await RecordWaivedSettlementUseCase().execute(command, uow)
        uow.settlements.save.assert_not_called()

    async def test_waive_wrong_direction_raises(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        # Bob owes Alice — waiving Alice→Bob is the wrong direction.
        tx = make_transaction(
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        uow = _setup_uow(alice, bob, transactions=[tx])

        command = RecordWaivedSettlementCommand(
            year=2026,
            month=1,
            from_person_id=alice.id,
            to_person_id=bob.id,
        )
        with pytest.raises(ValidationError, match="direction"):
            await RecordWaivedSettlementUseCase().execute(command, uow)
        uow.settlements.save.assert_not_called()

    async def test_missing_upload_adds_warning(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        uow = _setup_uow(alice, bob, transactions=[tx], uploads_for=[alice.id])

        command = RecordWaivedSettlementCommand(
            year=2026,
            month=1,
            from_person_id=bob.id,
            to_person_id=alice.id,
        )
        result = await RecordWaivedSettlementUseCase().execute(command, uow)

        assert result.settlement.is_waived is True
        assert any("No upload from Bob" in w for w in result.warnings)

    async def test_person_not_found_raises(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = make_mock_uow()
        uow.persons.get_by_ids.return_value = []

        command = RecordWaivedSettlementCommand(
            year=2026,
            month=1,
            from_person_id=alice.id,
            to_person_id=bob.id,
        )
        with pytest.raises(NotFoundError):
            await RecordWaivedSettlementUseCase().execute(command, uow)
