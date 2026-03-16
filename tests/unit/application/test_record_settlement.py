from decimal import Decimal

import pytest

from src.application.use_cases.record_settlement import (
    RecordSettlementCommand,
    RecordSettlementUseCase,
)
from src.domain.entities.settlement import SettlementMethod
from src.domain.exceptions import NotFoundError, ValidationError
from tests.fixtures.factories import make_person, make_transaction
from tests.fixtures.mocks import make_mock_uow, set_passthrough_save


class TestRecordSettlement:
    async def test_records_settlement(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = make_mock_uow()
        uow.persons.get_by_id.side_effect = lambda id: alice if id == alice.id else bob
        set_passthrough_save(uow)

        command = RecordSettlementCommand(
            year=2026,
            month=1,
            amount=Decimal("50.00"),
            from_person_id=alice.id,
            to_person_id=bob.id,
            method=SettlementMethod.VENMO,
        )
        result = await RecordSettlementUseCase().execute(command, uow)
        assert result.settlement.amount == Decimal("50.00")
        assert result.settlement.method == SettlementMethod.VENMO
        assert result.settlement.is_waived is False
        uow.settlements.save.assert_called_once()
        uow.commit.assert_called_once()

    async def test_same_person_raises_validation_error(self) -> None:
        alice = make_person(name="Alice")
        uow = make_mock_uow()
        command = RecordSettlementCommand(
            year=2026,
            month=1,
            amount=Decimal("50.00"),
            from_person_id=alice.id,
            to_person_id=alice.id,
            method=SettlementMethod.VENMO,
        )
        with pytest.raises(ValidationError, match="must differ"):
            await RecordSettlementUseCase().execute(command, uow)

    async def test_person_not_found_raises(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = make_mock_uow()
        uow.persons.get_by_id.return_value = None

        command = RecordSettlementCommand(
            year=2026,
            month=1,
            amount=Decimal("50.00"),
            from_person_id=alice.id,
            to_person_id=bob.id,
            method=SettlementMethod.VENMO,
        )
        with pytest.raises(NotFoundError):
            await RecordSettlementUseCase().execute(command, uow)

    async def test_links_transactions(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(payer_person_id=alice.id)
        uow = make_mock_uow()
        uow.persons.get_by_id.side_effect = lambda id: alice if id == alice.id else bob
        set_passthrough_save(uow)
        uow.transactions.get_by_ids.return_value = [tx]
        uow.transactions.update_mutable_fields.return_value = tx

        command = RecordSettlementCommand(
            year=2026,
            month=1,
            amount=Decimal("50.00"),
            from_person_id=alice.id,
            to_person_id=bob.id,
            method=SettlementMethod.VENMO,
            linked_transaction_ids=[tx.id],
        )
        await RecordSettlementUseCase().execute(command, uow)
        uow.settlement_transaction_links.save_batch.assert_called_once()
        uow.transactions.update_mutable_fields.assert_called_once()
