from datetime import date
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
    make_reconciliation_period,
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
    uow.transactions.get_all_settlement_relevant.return_value = transactions or []
    uow.categories.get_all.return_value = [category]
    uow.category_groups.get_all.return_value = [group]
    uow.settlements.get_all.return_value = settlements or []
    uow.settlement_transaction_links.get_by_settlement_ids.return_value = []
    uow.uploads.get_by_person_ids_with_transactions_in_date_range.return_value = [
        make_upload(person_id=pid) for pid in (uploads_for or [alice.id, bob.id])
    ]
    set_passthrough_save(uow)
    return uow


class TestRecordWaivedSettlement:
    async def test_waiver_persists_outstanding_balance(self) -> None:
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
        assert result.settlement.year == 2026
        assert result.settlement.month == 1
        assert result.warnings == []
        uow.settlements.save.assert_called_once()

    async def test_waiver_without_annotation(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        uow = _setup_uow(alice, bob, transactions=[tx])

        command = RecordWaivedSettlementCommand(
            from_person_id=bob.id,
            to_person_id=alice.id,
        )
        result = await RecordWaivedSettlementUseCase().execute(command, uow)

        assert result.settlement.amount == Decimal("50.00")
        assert result.settlement.year is None
        assert result.settlement.month is None

    async def test_waive_covers_multiple_months(self) -> None:
        """Waive applies to the total outstanding across all months —
        generalizing v1.7.0's per-month waiver."""
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        txs = [
            make_transaction(
                date=date(2026, 1, 15),
                payer_person_id=alice.id,
                amount=Decimal("-100.00"),
                payer_percentage=50,
            ),
            make_transaction(
                date=date(2026, 2, 10),
                payer_person_id=alice.id,
                amount=Decimal("-60.00"),
                payer_percentage=50,
            ),
        ]
        uow = _setup_uow(alice, bob, transactions=txs)

        command = RecordWaivedSettlementCommand(
            from_person_id=bob.id,
            to_person_id=alice.id,
        )
        result = await RecordWaivedSettlementUseCase().execute(command, uow)

        # $50 (January) + $30 (February) outstanding, waived in one record.
        assert result.settlement.amount == Decimal("80.00")
        assert result.settlement.is_waived is True

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

    async def test_missing_upload_in_span_newest_month_adds_warning(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            date=date(2026, 2, 10),
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        uow = _setup_uow(alice, bob, transactions=[tx], uploads_for=[alice.id])

        command = RecordWaivedSettlementCommand(
            from_person_id=bob.id,
            to_person_id=alice.id,
        )
        result = await RecordWaivedSettlementUseCase().execute(command, uow)

        assert result.settlement.is_waived is True
        assert any("No upload from Bob" in w for w in result.warnings)
        # Upload status was checked for the span's newest month (Feb 2026).
        call = uow.uploads.get_by_person_ids_with_transactions_in_date_range.call_args
        assert call.args[1] == date(2026, 2, 1)
        assert call.args[2] == date(2026, 2, 28)

    async def test_annotation_requires_both_year_and_month(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        with pytest.raises(ValueError, match="together"):
            RecordWaivedSettlementCommand(
                year=2026,
                from_person_id=bob.id,
                to_person_id=alice.id,
            )

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


async def test_waive_allowed_on_finalized_month() -> None:
    """Lock Month freezes transactions, not payments (v1.7.5): waiving the
    outstanding balance succeeds even when the annotated month is locked."""
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    tx = make_transaction(
        payer_person_id=alice.id,
        amount=Decimal("-100.00"),
        payer_percentage=50,
    )
    uow = _setup_uow(alice, bob, transactions=[tx])
    uow.reconciliation_periods.get_by_period.return_value = make_reconciliation_period(
        year=2026, month=1, is_finalized=True
    )

    command = RecordWaivedSettlementCommand(
        year=2026,
        month=1,
        from_person_id=bob.id,
        to_person_id=alice.id,
    )
    result = await RecordWaivedSettlementUseCase().execute(command, uow)
    assert result.settlement.is_waived is True
    uow.settlements.save.assert_called_once()


class TestYearScopedWaive:
    """``waive_year`` forgives one calendar year; omitting it keeps the
    all-time behaviour the chat tool relies on."""

    @staticmethod
    def _debt(year: int, month: int, payer: Person, amount: str):
        return make_transaction(
            date=date(year, month, 15),
            payer_person_id=payer.id,
            amount=Decimal(amount),
            payer_percentage=50,
        )

    async def test_waives_only_the_requested_year(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = _setup_uow(
            alice,
            bob,
            transactions=[
                self._debt(2025, 12, alice, "-100.00"),
                self._debt(2026, 3, alice, "-400.00"),
            ],
            settlements=[
                make_settlement(
                    amount=Decimal("50.00"),
                    from_person_id=bob.id,
                    to_person_id=alice.id,
                )
            ],
        )

        # The $50 payment clears 2025 (FIFO), leaving 2026's $200.
        command = RecordWaivedSettlementCommand(
            from_person_id=bob.id, to_person_id=alice.id, waive_year=2026
        )
        result = await RecordWaivedSettlementUseCase().execute(command, uow)

        assert result.settlement.amount == Decimal("200.00")
        assert result.settlement.is_waived is True

    async def test_refuses_while_an_older_year_is_open(self) -> None:
        """A waiver relieves the oldest open month first, so waiving a newer
        year over an older debt would forgive the wrong one."""
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = _setup_uow(
            alice,
            bob,
            transactions=[
                self._debt(2025, 12, alice, "-100.00"),
                self._debt(2026, 3, alice, "-400.00"),
            ],
        )

        command = RecordWaivedSettlementCommand(
            from_person_id=bob.id, to_person_id=alice.id, waive_year=2026
        )
        with pytest.raises(ValidationError, match="Settle or waive 2025 first"):
            await RecordWaivedSettlementUseCase().execute(command, uow)

    async def test_rejects_a_year_with_nothing_outstanding(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = _setup_uow(
            alice,
            bob,
            transactions=[self._debt(2026, 3, alice, "-400.00")],
            settlements=[
                make_settlement(
                    amount=Decimal("200.00"),
                    from_person_id=bob.id,
                    to_person_id=alice.id,
                )
            ],
        )

        command = RecordWaivedSettlementCommand(
            from_person_id=bob.id, to_person_id=alice.id, waive_year=2026
        )
        with pytest.raises(ValidationError, match="2026 is already settled"):
            await RecordWaivedSettlementUseCase().execute(command, uow)

    async def test_rejects_a_direction_the_year_does_not_owe(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = _setup_uow(
            alice, bob, transactions=[self._debt(2026, 3, alice, "-400.00")]
        )

        command = RecordWaivedSettlementCommand(
            from_person_id=alice.id, to_person_id=bob.id, waive_year=2026
        )
        with pytest.raises(ValidationError, match="does not match"):
            await RecordWaivedSettlementUseCase().execute(command, uow)
