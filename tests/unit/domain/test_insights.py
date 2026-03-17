from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.insights import compute_spending_trends
from tests.fixtures.factories import (
    make_transaction,
)


def _setup_groups() -> tuple[UUID, UUID, dict[str, tuple[UUID, str]]]:
    food_id = uuid4()
    travel_id = uuid4()
    lookup: dict[str, tuple[UUID, str]] = {
        "Dining Out": (food_id, "Food & Dining"),
        "Groceries": (food_id, "Food & Dining"),
        "Flights": (travel_id, "Travel"),
    }
    return food_id, travel_id, lookup


class TestComputeSpendingTrends:
    def test_empty_input(self) -> None:
        result = compute_spending_trends([], {}, 2026)
        assert result.monthly_group_spending == []
        assert result.monthly_totals == []
        assert result.group_summaries == []

    def test_single_month_single_group(self) -> None:
        food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-40.00")
            ),
            make_transaction(
                date=date(2026, 1, 20), category="Groceries", amount=Decimal("-60.00")
            ),
        ]

        result = compute_spending_trends(txs, lookup, 2026)

        assert len(result.monthly_group_spending) == 1
        mgs = result.monthly_group_spending[0]
        assert mgs.year == 2026
        assert mgs.month == 1
        assert mgs.group_id == food_id
        assert mgs.amount == Decimal("100.00")

        assert len(result.monthly_totals) == 1
        assert result.monthly_totals[0].total_amount == Decimal("100.00")

        assert len(result.group_summaries) == 1
        assert result.group_summaries[0].ytd_total == Decimal("100.00")
        assert result.group_summaries[0].transaction_count == 2

    def test_multiple_months_multiple_groups(self) -> None:
        food_id, travel_id, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-40.00")
            ),
            make_transaction(
                date=date(2026, 1, 15), category="Flights", amount=Decimal("-300.00")
            ),
            make_transaction(
                date=date(2026, 2, 5), category="Groceries", amount=Decimal("-80.00")
            ),
            make_transaction(
                date=date(2026, 2, 10), category="Flights", amount=Decimal("-200.00")
            ),
        ]

        result = compute_spending_trends(txs, lookup, 2026)

        assert len(result.monthly_group_spending) == 4  # 2 groups x 2 months
        assert len(result.monthly_totals) == 2

        jan_total = next(t for t in result.monthly_totals if t.month == 1)
        feb_total = next(t for t in result.monthly_totals if t.month == 2)
        assert jan_total.total_amount == Decimal("340.00")
        assert feb_total.total_amount == Decimal("280.00")

        # Group summaries sorted by YTD descending
        assert result.group_summaries[0].group_id == travel_id
        assert result.group_summaries[0].ytd_total == Decimal("500.00")
        assert result.group_summaries[1].group_id == food_id
        assert result.group_summaries[1].ytd_total == Decimal("120.00")

    def test_month_gaps(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-50.00")
            ),
            make_transaction(
                date=date(2026, 3, 10), category="Dining Out", amount=Decimal("-70.00")
            ),
        ]

        result = compute_spending_trends(txs, lookup, 2026)

        months = [t.month for t in result.monthly_totals]
        assert months == [1, 3]  # Feb is absent, not zero-filled

    def test_unmapped_categories(self) -> None:
        lookup: dict[str, tuple[UUID, str]] = {}  # nothing mapped
        txs = [
            make_transaction(
                date=date(2026, 1, 10),
                category="Mystery Store",
                amount=Decimal("-25.00"),
            ),
        ]

        result = compute_spending_trends(txs, lookup, 2026)

        assert len(result.group_summaries) == 1
        assert result.group_summaries[0].group_id is None
        assert result.group_summaries[0].group_name == "Uncategorized"

    def test_refunds_excluded(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-50.00")
            ),
            make_transaction(
                date=date(2026, 1, 15), category="Dining Out", amount=Decimal("20.00")
            ),  # refund
        ]

        result = compute_spending_trends(txs, lookup, 2026)

        assert len(result.monthly_totals) == 1
        assert result.monthly_totals[0].total_amount == Decimal("50.00")

    def test_non_shared_excluded(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-50.00")
            ),
            make_transaction(
                date=date(2026, 1, 15),
                category="Dining Out",
                amount=Decimal("-30.00"),
                payer_percentage=None,
            ),  # not shared
        ]

        result = compute_spending_trends(txs, lookup, 2026)

        assert result.monthly_totals[0].total_amount == Decimal("50.00")

    def test_group_summaries_sorted_descending(self) -> None:
        food_id, travel_id, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-100.00")
            ),
            make_transaction(
                date=date(2026, 1, 10), category="Flights", amount=Decimal("-50.00")
            ),
        ]

        result = compute_spending_trends(txs, lookup, 2026)

        assert result.group_summaries[0].group_id == food_id
        assert result.group_summaries[1].group_id == travel_id
