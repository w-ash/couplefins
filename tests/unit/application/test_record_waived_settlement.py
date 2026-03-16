from decimal import Decimal

import pytest

from src.application.use_cases.record_waived_settlement import (
    RecordWaivedSettlementCommand,
    RecordWaivedSettlementUseCase,
)
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import make_person
from tests.fixtures.mocks import make_mock_uow, set_passthrough_save


class TestRecordWaivedSettlement:
    async def test_waives_balance(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = make_mock_uow()
        uow.persons.get_by_id.side_effect = lambda id: alice if id == alice.id else bob
        set_passthrough_save(uow)

        command = RecordWaivedSettlementCommand(
            year=2026,
            month=1,
            from_person_id=alice.id,
            to_person_id=bob.id,
            notes="Forgiven",
        )
        result = await RecordWaivedSettlementUseCase().execute(command, uow)
        assert result.settlement.amount == Decimal(0)
        assert result.settlement.is_waived is True
        assert result.settlement.method is None
        uow.settlements.save.assert_called_once()

    async def test_person_not_found_raises(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = make_mock_uow()
        uow.persons.get_by_id.return_value = None

        command = RecordWaivedSettlementCommand(
            year=2026,
            month=1,
            from_person_id=alice.id,
            to_person_id=bob.id,
        )
        with pytest.raises(NotFoundError):
            await RecordWaivedSettlementUseCase().execute(command, uow)
