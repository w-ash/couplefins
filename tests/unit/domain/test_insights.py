from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.insights import (
    compute_comparison_cards,
    compute_person_paid_by_month,
    compute_spending_trends,
    compute_trailing_average,
)
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

    def test_non_household_excluded(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-50.00")
            ),
            make_transaction(
                date=date(2026, 1, 15),
                category="Dining Out",
                amount=Decimal("-30.00"),
                payer_percentage=100,
                household=False,
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

    def test_categories_populated(self) -> None:
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

        mgs = result.monthly_group_spending[0]
        assert mgs.group_id == food_id
        assert len(mgs.categories) == 2
        cat_names = {c.category for c in mgs.categories}
        assert cat_names == {"Dining Out", "Groceries"}
        cat_amounts = {c.category: c.amount for c in mgs.categories}
        assert cat_amounts["Dining Out"] == Decimal("40.00")
        assert cat_amounts["Groceries"] == Decimal("60.00")


class TestComputeTrailingAverage:
    def test_normal_three_month_window(self) -> None:
        food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-100.00")
            ),
            make_transaction(
                date=date(2026, 2, 10), category="Dining Out", amount=Decimal("-200.00")
            ),
            make_transaction(
                date=date(2026, 3, 10), category="Dining Out", amount=Decimal("-150.00")
            ),
            make_transaction(
                date=date(2026, 4, 10), category="Dining Out", amount=Decimal("-300.00")
            ),
        ]

        result = compute_trailing_average(txs, lookup, target_month=4, window=3)

        assert food_id in result
        # Average of months 1-3: (100 + 200 + 150) / 3 = 150
        assert result[food_id] == Decimal("150.00")

    def test_fewer_months_than_window(self) -> None:
        food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-100.00")
            ),
            make_transaction(
                date=date(2026, 3, 10), category="Dining Out", amount=Decimal("-50.00")
            ),
        ]

        result = compute_trailing_average(txs, lookup, target_month=3, window=3)

        # Only month 1 is before target month 3
        assert result[food_id] == Decimal("100.00")

    def test_target_month_one_returns_empty(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-100.00")
            ),
        ]

        result = compute_trailing_average(txs, lookup, target_month=1)

        assert result == {}

    def test_month_gaps(self) -> None:
        food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-100.00")
            ),
            make_transaction(
                date=date(2026, 3, 10), category="Dining Out", amount=Decimal("-200.00")
            ),
            # Month 2 has no data
        ]

        result = compute_trailing_average(txs, lookup, target_month=4, window=3)

        # Months 1 and 3 have data, window=3 but only 2 available: (100+200)/2
        assert result[food_id] == Decimal("150.00")

    def test_multiple_groups(self) -> None:
        food_id, travel_id, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-100.00")
            ),
            make_transaction(
                date=date(2026, 1, 15), category="Flights", amount=Decimal("-300.00")
            ),
            make_transaction(
                date=date(2026, 2, 10), category="Dining Out", amount=Decimal("-200.00")
            ),
        ]

        result = compute_trailing_average(txs, lookup, target_month=3, window=3)

        assert result[food_id] == Decimal("150.00")  # (100+200)/2
        assert result[travel_id] == Decimal(
            "150.00"
        )  # 300/2 (present in month 1, window covers months 1+2)

    def test_empty_input(self) -> None:
        result = compute_trailing_average([], {}, target_month=3)
        assert result == {}


class TestComputeComparisonCards:
    def test_above_average(self) -> None:
        food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-100.00")
            ),
            make_transaction(
                date=date(2026, 2, 10), category="Dining Out", amount=Decimal("-100.00")
            ),
            make_transaction(
                date=date(2026, 3, 10), category="Dining Out", amount=Decimal("-200.00")
            ),
        ]

        cards = compute_comparison_cards(txs, lookup, target_month=3)

        assert len(cards) == 1
        card = cards[0]
        assert card.group_id == food_id
        assert card.current_month_amount == Decimal("200.00")
        assert card.trailing_average == Decimal("100.00")
        assert card.delta_amount == Decimal("100.00")
        assert card.delta_percentage == Decimal(100)
        assert card.is_new is False

    def test_below_average(self) -> None:
        _food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-200.00")
            ),
            make_transaction(
                date=date(2026, 2, 10), category="Dining Out", amount=Decimal("-200.00")
            ),
            make_transaction(
                date=date(2026, 3, 10), category="Dining Out", amount=Decimal("-100.00")
            ),
        ]

        cards = compute_comparison_cards(txs, lookup, target_month=3)

        card = cards[0]
        assert card.delta_amount == Decimal("-100.00")
        assert card.delta_percentage == Decimal(-50)
        assert card.is_new is False

    def test_current_month_only_no_trailing(self) -> None:
        _food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-100.00")
            ),
        ]

        cards = compute_comparison_cards(txs, lookup, target_month=1)

        assert len(cards) == 1
        card = cards[0]
        assert card.current_month_amount == Decimal("100.00")
        assert card.trailing_average == Decimal(0)
        assert card.delta_percentage == Decimal(0)
        assert card.is_new is True

    def test_trailing_only_no_current(self) -> None:
        _food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-100.00")
            ),
        ]

        cards = compute_comparison_cards(txs, lookup, target_month=2)

        assert len(cards) == 1
        card = cards[0]
        assert card.current_month_amount == Decimal(0)
        assert card.trailing_average == Decimal("100.00")
        assert card.is_new is False

    def test_empty_returns_empty(self) -> None:
        cards = compute_comparison_cards([], {}, target_month=3)
        assert cards == []

    def test_sorted_by_abs_delta_percentage(self) -> None:
        food_id, travel_id, lookup = _setup_groups()
        txs = [
            # Food: avg 100, current 110 → +10%
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-100.00")
            ),
            make_transaction(
                date=date(2026, 2, 10), category="Dining Out", amount=Decimal("-110.00")
            ),
            # Travel: avg 200, current 300 → +50%
            make_transaction(
                date=date(2026, 1, 15), category="Flights", amount=Decimal("-200.00")
            ),
            make_transaction(
                date=date(2026, 2, 15), category="Flights", amount=Decimal("-300.00")
            ),
        ]

        cards = compute_comparison_cards(txs, lookup, target_month=2)

        assert cards[0].group_id == travel_id  # 50% delta > 10%
        assert cards[1].group_id == food_id

    def test_new_group_sorts_before_existing_percentage_deltas(self) -> None:
        food_id, travel_id, lookup = _setup_groups()
        txs = [
            # Food: avg 100, current 110 → +10% (existing group, small % swing)
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-100.00")
            ),
            make_transaction(
                date=date(2026, 2, 10), category="Dining Out", amount=Decimal("-110.00")
            ),
            # Travel: brand new this month, avg 0 → "+0%" under the old bug,
            # but represents real new spending and should rank first.
            make_transaction(
                date=date(2026, 2, 15), category="Flights", amount=Decimal("-800.00")
            ),
        ]

        cards = compute_comparison_cards(txs, lookup, target_month=2)

        assert cards[0].group_id == travel_id
        assert cards[0].is_new is True
        assert cards[1].group_id == food_id
        assert cards[1].is_new is False

    def test_new_groups_tie_broken_by_dollar_delta(self) -> None:
        food_id, travel_id, lookup = _setup_groups()
        txs = [
            # Both groups are brand new this month (no trailing average).
            make_transaction(
                date=date(2026, 2, 10), category="Dining Out", amount=Decimal("-50.00")
            ),
            make_transaction(
                date=date(2026, 2, 15), category="Flights", amount=Decimal("-500.00")
            ),
        ]

        cards = compute_comparison_cards(txs, lookup, target_month=2)

        assert cards[0].group_id == travel_id
        assert cards[1].group_id == food_id
        assert all(c.is_new for c in cards)


class TestComputePersonPaidByMonth:
    def test_two_payers_one_month(self) -> None:
        food_id, _, lookup = _setup_groups()
        alice = uuid4()
        bob = uuid4()
        txs = [
            make_transaction(
                date=date(2026, 1, 10),
                category="Dining Out",
                amount=Decimal("-60.00"),
                payer_person_id=alice,
            ),
            make_transaction(
                date=date(2026, 1, 20),
                category="Groceries",
                amount=Decimal("-40.00"),
                payer_person_id=bob,
            ),
        ]

        result = compute_person_paid_by_month(txs, lookup)

        by_person = {r.person_id: r for r in result}
        assert by_person[alice].month == 1
        assert by_person[alice].group_id == food_id
        assert by_person[alice].amount_paid == Decimal("60.00")
        assert by_person[bob].amount_paid == Decimal("40.00")

    def test_multiple_months(self) -> None:
        _, _, lookup = _setup_groups()
        alice = uuid4()
        txs = [
            make_transaction(
                date=date(2026, 1, 10),
                category="Dining Out",
                amount=Decimal("-50.00"),
                payer_person_id=alice,
            ),
            make_transaction(
                date=date(2026, 2, 10),
                category="Dining Out",
                amount=Decimal("-70.00"),
                payer_person_id=alice,
            ),
        ]

        result = compute_person_paid_by_month(txs, lookup)

        months = {r.month: r.amount_paid for r in result}
        assert months[1] == Decimal("50.00")
        assert months[2] == Decimal("70.00")

    def test_empty_returns_empty(self) -> None:
        result = compute_person_paid_by_month([], {})
        assert result == []

    def test_groups_by_category_group(self) -> None:
        food_id, travel_id, lookup = _setup_groups()
        alice = uuid4()
        txs = [
            make_transaction(
                date=date(2026, 1, 10),
                category="Dining Out",
                amount=Decimal("-30.00"),
                payer_person_id=alice,
            ),
            make_transaction(
                date=date(2026, 1, 15),
                category="Flights",
                amount=Decimal("-200.00"),
                payer_person_id=alice,
            ),
        ]

        result = compute_person_paid_by_month(txs, lookup)

        by_group = {r.group_id: r.amount_paid for r in result}
        assert by_group[food_id] == Decimal("30.00")
        assert by_group[travel_id] == Decimal("200.00")

    def test_unmapped_category_has_none_group_id(self) -> None:
        _, _, lookup = _setup_groups()
        alice = uuid4()
        txs = [
            make_transaction(
                date=date(2026, 1, 10),
                category="Dining Out",
                amount=Decimal("-40.00"),
                payer_person_id=alice,
            ),
            make_transaction(
                date=date(2026, 1, 15),
                category="Mystery Store",  # not in lookup
                amount=Decimal("-25.00"),
                payer_person_id=alice,
            ),
        ]

        result = compute_person_paid_by_month(txs, lookup)

        by_group = {r.group_id: r.amount_paid for r in result}
        assert by_group[None] == Decimal("25.00")


class TestExcludedTransactions:
    def test_excluded_not_in_spending_trends(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10),
                category="Dining Out",
                amount=Decimal("-50.00"),
            ),
            make_transaction(
                date=date(2026, 1, 15),
                category="Dining Out",
                amount=Decimal("-30.00"),
                is_excluded=True,
            ),
        ]

        result = compute_spending_trends(txs, lookup, 2026)

        assert result.monthly_totals[0].total_amount == Decimal("50.00")

    def test_excluded_not_in_comparison_cards(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 2, 10),
                category="Dining Out",
                amount=Decimal("-50.00"),
            ),
            make_transaction(
                date=date(2026, 2, 15),
                category="Dining Out",
                amount=Decimal("-40.00"),
                is_excluded=True,
            ),
        ]

        cards = compute_comparison_cards(txs, lookup, target_month=2)
        assert cards[0].current_month_amount == Decimal("50.00")
