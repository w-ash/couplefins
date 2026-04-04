from datetime import date
from decimal import Decimal

from src.application.use_cases.find_settlement_candidates import (
    FindSettlementCandidatesCommand,
    FindSettlementCandidatesUseCase,
)
from tests.fixtures.factories import make_settlement_merchant, make_transaction
from tests.fixtures.mocks import make_mock_uow


class TestFindSettlementCandidates:
    async def test_returns_candidates(self) -> None:
        tx = make_transaction(
            merchant="Venmo",
            amount=Decimal("-100.00"),
            household=False,
            date=date(2026, 3, 15),
        )
        merchant = make_settlement_merchant(name="Venmo", merchant_pattern="venmo")
        uow = make_mock_uow()
        uow.transactions.get_by_date_range.return_value = [tx]
        uow.settlement_merchants.get_all.return_value = [merchant]

        command = FindSettlementCandidatesCommand(
            year=2026, month=3, amount=Decimal("100.00")
        )
        result = await FindSettlementCandidatesUseCase().execute(command, uow)
        assert len(result.candidates) == 1
        assert result.candidates[0].transaction.id == tx.id

    async def test_date_range_crosses_month_boundary(self) -> None:
        uow = make_mock_uow()
        uow.transactions.get_by_date_range.return_value = []
        uow.settlement_merchants.get_all.return_value = []

        command = FindSettlementCandidatesCommand(
            year=2026, month=1, amount=Decimal("50.00")
        )
        await FindSettlementCandidatesUseCase().execute(command, uow)

        call_args = uow.transactions.get_by_date_range.call_args
        start, end = call_args.args[0], call_args.args[1]
        assert start == date(2025, 12, 25)
        assert end == date(2026, 2, 7)

    async def test_empty_transactions(self) -> None:
        uow = make_mock_uow()
        uow.transactions.get_by_date_range.return_value = []
        uow.settlement_merchants.get_all.return_value = []

        command = FindSettlementCandidatesCommand(
            year=2026, month=3, amount=Decimal("100.00")
        )
        result = await FindSettlementCandidatesUseCase().execute(command, uow)
        assert result.candidates == []
