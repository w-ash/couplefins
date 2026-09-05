from datetime import date
from decimal import Decimal

import pytest

from src.application.use_cases import find_settlement_candidates as fsc
from src.application.use_cases.find_settlement_candidates import (
    FindSettlementCandidatesCommand,
    FindSettlementCandidatesUseCase,
)
from tests.fixtures.factories import (
    make_category,
    make_category_group,
    make_person,
    make_settlement_merchant,
    make_transaction,
)
from tests.fixtures.mocks import make_mock_uow


def _freeze_today(monkeypatch: pytest.MonkeyPatch, frozen: date) -> None:
    """Pin the clock so window assertions are literal dates, not a mirror of
    the production formula (and immune to UTC-midnight races)."""
    monkeypatch.setattr(fsc, "_today", lambda: frozen)


class TestFindSettlementCandidates:
    async def test_returns_candidates_over_outstanding_span(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Today is past the span's end → the window clamps to today.
        _freeze_today(monkeypatch, date(2026, 4, 15))
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = make_mock_uow()
        uow.persons.get_all.return_value = [alice, bob]
        uow.categories.get_all.return_value = []
        uow.category_groups.get_all.return_value = []
        # Outstanding March balance → span = (2026-03, 2026-03).
        uow.transactions.get_all_settlement_relevant.return_value = [
            make_transaction(
                date=date(2026, 3, 10),
                payer_person_id=alice.id,
                amount=Decimal("-200.00"),
                payer_percentage=50,
            )
        ]
        tx = make_transaction(
            merchant="Venmo",
            amount=Decimal("-100.00"),
            household=False,
            date=date(2026, 3, 15),
        )
        merchant = make_settlement_merchant(name="Venmo", merchant_pattern="venmo")
        uow.transactions.get_by_date_range.return_value = [tx]
        uow.settlement_merchants.get_all.return_value = [merchant]

        command = FindSettlementCandidatesCommand(amount=Decimal("100.00"))
        result = await FindSettlementCandidatesUseCase().execute(command, uow)
        assert len(result.candidates) == 1
        assert result.candidates[0].transaction.id == tx.id

        # Window: span start (month begin) → today (+ 7-day padding), so a
        # transfer dated after the outstanding span still surfaces.
        call_args = uow.transactions.get_by_date_range.call_args
        assert call_args.args[0] == date(2026, 3, 1)
        assert call_args.args[1] == date(2026, 4, 22)  # 2026-04-15 + 7 days

    async def test_span_covers_multiple_outstanding_months(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Today is inside the span → the span's own end wins the clamp.
        _freeze_today(monkeypatch, date(2026, 2, 1))
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = make_mock_uow()
        uow.persons.get_all.return_value = [alice, bob]
        uow.categories.get_all.return_value = []
        uow.category_groups.get_all.return_value = []
        uow.transactions.get_all_settlement_relevant.return_value = [
            make_transaction(
                date=date(2026, 1, 10),
                payer_person_id=alice.id,
                amount=Decimal("-100.00"),
                payer_percentage=50,
            ),
            make_transaction(
                date=date(2026, 3, 10),
                payer_person_id=alice.id,
                amount=Decimal("-100.00"),
                payer_percentage=50,
            ),
        ]
        uow.transactions.get_by_date_range.return_value = []
        uow.settlement_merchants.get_all.return_value = []

        command = FindSettlementCandidatesCommand(amount=Decimal("100.00"))
        await FindSettlementCandidatesUseCase().execute(command, uow)

        call_args = uow.transactions.get_by_date_range.call_args
        assert call_args.args[0] == date(2026, 1, 1)
        assert call_args.args[1] == date(2026, 4, 7)  # 2026-03-31 + 7 days

    async def test_transfer_kind_category_rows_stay_candidates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Venmo legs live in the Transfer group — excluded from spending, but
        the candidate finder must still see them."""
        _freeze_today(monkeypatch, date(2026, 4, 15))
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = make_mock_uow()
        uow.persons.get_all.return_value = [alice, bob]
        transfer_group = make_category_group(name="Transfer", kind="transfer")
        uow.categories.get_all.return_value = [
            make_category(name="Transfer", group_id=transfer_group.id)
        ]
        uow.category_groups.get_all.return_value = [transfer_group]
        uow.transactions.get_all_settlement_relevant.return_value = [
            make_transaction(
                date=date(2026, 3, 10),
                payer_person_id=alice.id,
                amount=Decimal("-200.00"),
                payer_percentage=50,
            )
        ]
        leg = make_transaction(
            merchant="Venmo",
            category="Transfer",
            amount=Decimal("-100.00"),
            household=False,
            date=date(2026, 4, 1),
        )
        uow.transactions.get_by_date_range.return_value = [leg]
        uow.settlement_merchants.get_all.return_value = [
            make_settlement_merchant(name="Venmo", merchant_pattern="venmo")
        ]

        command = FindSettlementCandidatesCommand(amount=Decimal("100.00"))
        result = await FindSettlementCandidatesUseCase().execute(command, uow)

        assert [c.transaction.id for c in result.candidates] == [leg.id]

    async def test_transfer_after_span_still_surfaces(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The couple owes an old March balance and settles it with a transfer
        # dated today (after the span) — it must appear in the default search.
        _freeze_today(monkeypatch, date(2026, 4, 15))
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = make_mock_uow()
        uow.persons.get_all.return_value = [alice, bob]
        uow.categories.get_all.return_value = []
        uow.category_groups.get_all.return_value = []
        uow.transactions.get_all_settlement_relevant.return_value = [
            make_transaction(
                date=date(2026, 3, 10),
                payer_person_id=alice.id,
                amount=Decimal("-200.00"),
                payer_percentage=50,
            )
        ]
        transfer = make_transaction(
            merchant="Venmo",
            amount=Decimal("-100.00"),
            household=False,
            date=date(2026, 4, 15),
        )
        uow.transactions.get_by_date_range.return_value = [transfer]
        uow.settlement_merchants.get_all.return_value = [
            make_settlement_merchant(name="Venmo", merchant_pattern="venmo")
        ]

        command = FindSettlementCandidatesCommand(amount=Decimal("100.00"))
        result = await FindSettlementCandidatesUseCase().execute(command, uow)

        assert [c.transaction.id for c in result.candidates] == [transfer.id]

    async def test_explicit_search_month_narrows_window(self) -> None:
        uow = make_mock_uow()
        uow.transactions.get_by_date_range.return_value = []
        uow.settlement_merchants.get_all.return_value = []

        command = FindSettlementCandidatesCommand(
            amount=Decimal("50.00"), search_year=2026, search_month=1
        )
        await FindSettlementCandidatesUseCase().execute(command, uow)

        call_args = uow.transactions.get_by_date_range.call_args
        assert call_args.args[0] == date(2026, 1, 1)
        assert call_args.args[1] == date(2026, 2, 7)
        # The narrow path never loads the ledger.
        uow.transactions.get_all_settlement_relevant.assert_not_called()

    async def test_nothing_outstanding_yields_no_candidates(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = make_mock_uow()
        uow.persons.get_all.return_value = [alice, bob]
        uow.categories.get_all.return_value = []
        uow.category_groups.get_all.return_value = []
        uow.transactions.get_all_settlement_relevant.return_value = []

        command = FindSettlementCandidatesCommand(amount=Decimal("100.00"))
        result = await FindSettlementCandidatesUseCase().execute(command, uow)
        assert result.candidates == []
        uow.transactions.get_by_date_range.assert_not_called()
