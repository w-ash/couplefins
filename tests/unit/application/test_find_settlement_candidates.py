from datetime import date
from decimal import Decimal

from src.application.use_cases.find_settlement_candidates import (
    FindSettlementCandidatesCommand,
    FindSettlementCandidatesUseCase,
)
from tests.fixtures.factories import (
    make_person,
    make_settlement_merchant,
    make_transaction,
)
from tests.fixtures.mocks import make_mock_uow


class TestFindSettlementCandidates:
    async def test_returns_candidates_over_outstanding_span(self) -> None:
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

        # Window: span start (month begin) → span end (month end) + 7 days.
        call_args = uow.transactions.get_by_date_range.call_args
        assert call_args.args[0] == date(2026, 3, 1)
        assert call_args.args[1] == date(2026, 4, 7)

    async def test_span_covers_multiple_outstanding_months(self) -> None:
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
        assert call_args.args[1] == date(2026, 4, 7)

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
