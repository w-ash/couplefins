from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.entities.transaction import Transaction
from src.domain.insights import (
    compute_category_comparisons,
    compute_comparison_cards,
    compute_spending_flow,
    compute_spending_trends,
    compute_trailing_average,
)
from tests.fixtures.factories import (
    ALICE,
    BOB,
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

    def test_refunds_net_against_spending(self) -> None:
        """Signed-amount convention, same as Budget and Dashboard."""
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
        assert result.monthly_totals[0].total_amount == Decimal("30.00")

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

    def test_through_month_bounds_ytd_but_not_monthly_lists(self) -> None:
        food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-50.00")
            ),
            make_transaction(
                date=date(2026, 2, 10), category="Dining Out", amount=Decimal("-70.00")
            ),
            make_transaction(
                date=date(2026, 3, 10), category="Dining Out", amount=Decimal("-900.00")
            ),
        ]

        result = compute_spending_trends(txs, lookup, 2026, through_month=2)

        # Per-month breakdown still covers the whole year...
        assert len(result.monthly_totals) == 3
        assert len(result.monthly_group_spending) == 3
        # ...but the YTD group summary stops at the selected month.
        assert len(result.group_summaries) == 1
        assert result.group_summaries[0].group_id == food_id
        assert result.group_summaries[0].ytd_total == Decimal("120.00")
        assert result.group_summaries[0].transaction_count == 2

    def test_through_month_none_is_unbounded(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-50.00")
            ),
            make_transaction(
                date=date(2026, 3, 10), category="Dining Out", amount=Decimal("-70.00")
            ),
        ]

        result = compute_spending_trends(txs, lookup, 2026, through_month=None)

        assert result.group_summaries[0].ytd_total == Decimal("120.00")

    def test_through_month_excludes_group_only_present_later(self) -> None:
        food_id, travel_id, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 1, 10), category="Dining Out", amount=Decimal("-50.00")
            ),
            # Travel only appears after the selected month.
            make_transaction(
                date=date(2026, 3, 10), category="Flights", amount=Decimal("-500.00")
            ),
        ]

        result = compute_spending_trends(txs, lookup, 2026, through_month=1)

        group_ids = {g.group_id for g in result.group_summaries}
        assert group_ids == {food_id}
        assert travel_id not in group_ids


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


class TestPersonalScope:
    """`person_id` switches every computation to that person's share."""

    @staticmethod
    def _ytd(
        txs: list[Transaction], lookup: dict[str, tuple[UUID, str]], pid: UUID | None
    ) -> dict[UUID | None, Decimal]:
        result = compute_spending_trends(txs, lookup, 2026, person_id=pid)
        return {g.group_id: g.ytd_total for g in result.group_summaries}

    def test_household_split_gives_each_person_their_share(self) -> None:
        food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                category="Dining Out",
                amount=Decimal("-100.00"),
                payer_person_id=ALICE.id,
                payer_percentage=50,
            ),
            make_transaction(
                category="Groceries",
                amount=Decimal("-200.00"),
                payer_person_id=BOB.id,
                payer_percentage=70,
            ),
        ]
        assert self._ytd(txs, lookup, ALICE.id) == {food_id: Decimal("110.00")}
        assert self._ytd(txs, lookup, BOB.id) == {food_id: Decimal("190.00")}
        assert self._ytd(txs, lookup, None) == {food_id: Decimal("300.00")}

    def test_personal_row_counts_only_for_its_owner(self) -> None:
        food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                category="Dining Out",
                amount=Decimal("-40.00"),
                payer_person_id=ALICE.id,
                payer_percentage=100,
                household=False,
                tags=(),
            )
        ]
        assert self._ytd(txs, lookup, ALICE.id) == {food_id: Decimal("40.00")}
        assert self._ytd(txs, lookup, BOB.id) == {}
        assert self._ytd(txs, lookup, None) == {}

    def test_spotted_row_lands_on_beneficiary(self) -> None:
        food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                category="Dining Out",
                amount=Decimal("-30.00"),
                payer_person_id=ALICE.id,
                payer_percentage=0,
                household=False,
                tags=("bob",),
            )
        ]
        assert self._ytd(txs, lookup, BOB.id) == {food_id: Decimal("30.00")}
        assert self._ytd(txs, lookup, ALICE.id) == {}

    def test_zero_share_household_row_is_dropped_entirely(self) -> None:
        """A partner-paid `s100` household row must not surface as a group
        with a transaction count but no amount (which would also make
        comparison cards flag it as new)."""
        _, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, 3, 5),
                category="Dining Out",
                amount=Decimal("-60.00"),
                payer_person_id=ALICE.id,
                payer_percentage=100,
            )
        ]
        result = compute_spending_trends(txs, lookup, 2026, person_id=BOB.id)
        assert result.group_summaries == []
        assert result.monthly_totals == []
        assert compute_comparison_cards(txs, lookup, 3, person_id=BOB.id) == []

    def test_refund_nets_the_persons_share(self) -> None:
        food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                category="Dining Out", amount=Decimal("25.00"), payer_person_id=ALICE.id
            )
        ]
        assert self._ytd(txs, lookup, ALICE.id) == {food_id: Decimal("-12.50")}
        assert self._ytd(txs, lookup, BOB.id) == {food_id: Decimal("-12.50")}

    def test_settlements_and_excluded_rows_ignored(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                category="Dining Out",
                amount=Decimal("-25.00"),
                payer_person_id=ALICE.id,
                is_settlement=True,
            ),
            make_transaction(
                category="Dining Out",
                amount=Decimal("-25.00"),
                payer_person_id=ALICE.id,
                is_excluded=True,
            ),
        ]
        assert self._ytd(txs, lookup, ALICE.id) == {}

    def test_partners_personal_views_sum_to_household_view(self) -> None:
        """Per-row shares are complementary, so the two personal views add
        up to the household view exactly — including odd cents."""
        food_id, travel_id, lookup = _setup_groups()
        txs = [
            make_transaction(
                category="Dining Out",
                amount=Decimal("-33.33"),
                payer_person_id=ALICE.id,
                payer_percentage=50,
            ),
            make_transaction(
                category="Flights",
                amount=Decimal("-99.99"),
                payer_person_id=BOB.id,
                payer_percentage=33,
            ),
        ]
        alice = self._ytd(txs, lookup, ALICE.id)
        bob = self._ytd(txs, lookup, BOB.id)
        household = self._ytd(txs, lookup, None)
        for gid in (food_id, travel_id):
            assert alice[gid] + bob[gid] == household[gid]

    def test_comparison_cards_and_trailing_average_use_the_lens(self) -> None:
        food_id, _, lookup = _setup_groups()
        txs = [
            make_transaction(
                date=date(2026, m, 5),
                category="Dining Out",
                amount=Decimal("-100.00"),
                payer_person_id=ALICE.id,
                payer_percentage=70,
            )
            for m in (1, 2, 3)
        ]
        avg = compute_trailing_average(txs, lookup, 3, person_id=BOB.id)
        assert avg == {food_id: Decimal("30.00")}

        cards = compute_comparison_cards(txs, lookup, 3, person_id=BOB.id)
        assert len(cards) == 1
        assert cards[0].current_month_amount == Decimal("30.00")
        assert cards[0].trailing_average == Decimal("30.00")
        assert cards[0].delta_amount == Decimal("0.00")


def _row(
    *,
    month: int = 1,
    day: int = 10,
    merchant: str = "Sushi Place",
    category: str = "Dining Out",
    amount: str = "-40.00",
    payer: UUID = ALICE.id,
    pct: int = 50,
    household: bool = True,
) -> Transaction:
    return make_transaction(
        date=date(2026, month, day),
        merchant=merchant,
        category=category,
        amount=Decimal(amount),
        payer_person_id=payer,
        payer_percentage=pct,
        household=household,
        tags=() if household else ("x",),
    )


class TestComputeSpendingFlow:
    def test_empty_input(self) -> None:
        _, _, lookup = _setup_groups()
        flow = compute_spending_flow([], lookup, months={1})
        assert (flow.cells, flow.top_merchants) == ([], [])

    def test_household_cells_are_keyed_by_payer_and_category(self) -> None:
        food_id, travel_id, lookup = _setup_groups()
        txs = [
            _row(amount="-40.00", payer=ALICE.id),
            _row(amount="-60.00", payer=BOB.id),
            _row(amount="-10.00", payer=ALICE.id, day=12),
            _row(category="Flights", amount="-300.00", payer=ALICE.id, pct=100),
        ]

        flow = compute_spending_flow(txs, lookup, months={1})

        assert [
            (
                c.source_kind,
                c.source_person_id,
                c.group_id,
                c.category,
                c.amount,
                c.transaction_count,
            )
            for c in flow.cells
        ] == [
            ("payer", ALICE.id, travel_id, "Flights", Decimal("300.00"), 1),
            ("payer", BOB.id, food_id, "Dining Out", Decimal("60.00"), 1),
            ("payer", ALICE.id, food_id, "Dining Out", Decimal("50.00"), 2),
        ]

    def test_refund_nets_against_the_payers_cell(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [_row(amount="-40.00"), _row(amount="15.00", day=20)]
        [cell] = compute_spending_flow(txs, lookup, months={1}).cells
        assert (cell.amount, cell.transaction_count) == (Decimal("25.00"), 2)

    def test_unmapped_category_is_uncategorized(self) -> None:
        _, _, lookup = _setup_groups()
        [cell] = compute_spending_flow(
            [_row(category="Mystery")], lookup, months={1}
        ).cells
        assert (cell.group_id, cell.group_name) == (None, "Uncategorized")

    def test_month_window_versus_year_to_date(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [
            _row(month=1),
            _row(month=2, amount="-20.00"),
            _row(month=3, amount="-5.00"),
        ]

        february = compute_spending_flow(txs, lookup, months={2})
        ytd = compute_spending_flow(txs, lookup, months=range(1, 3))

        assert sum(c.amount for c in february.cells) == Decimal("20.00")
        assert sum(c.amount for c in ytd.cells) == Decimal("60.00")

    def test_personal_lens_names_the_viewers_claim(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [
            _row(amount="-100.00", payer=BOB.id, pct=50),  # my half
            _row(amount="-40.00", payer=ALICE.id, pct=100, household=False),  # mine
            _row(amount="-30.00", payer=BOB.id, pct=0, household=False),  # spotted
            _row(amount="-99.00", payer=BOB.id, pct=100, household=False),  # theirs
            _row(amount="-50.00", payer=BOB.id, pct=100),  # their own ticket
            _row(amount="-12.00", payer=ALICE.id, pct=0, household=False),  # I spotted
        ]

        flow = compute_spending_flow(txs, lookup, person_id=ALICE.id, months={1})

        assert {(c.source_kind, c.source_person_id, c.amount) for c in flow.cells} == {
            ("household_share", BOB.id, Decimal("50.00")),
            ("personal", ALICE.id, Decimal("40.00")),
            ("spotted_for_me", BOB.id, Decimal("30.00")),
        }

    def test_top_merchants_sorted_limited_and_refund_only_dropped(self) -> None:
        food_id, _, lookup = _setup_groups()
        txs = [
            _row(merchant="Sushi Place", amount="-40.00"),
            _row(merchant="Sushi Place", amount="-30.00", day=11, category="Groceries"),
            _row(merchant="Sushi Place", amount="-35.00", day=12),
            _row(merchant="Grocer", amount="-90.00", category="Groceries"),
            _row(merchant="Airline", amount="-500.00", category="Flights"),
            _row(merchant="Refunder", amount="25.00"),
        ]

        flow = compute_spending_flow(txs, lookup, months={1}, merchant_limit=2)

        assert [
            (m.merchant, m.amount, m.transaction_count) for m in flow.top_merchants
        ] == [
            ("Airline", Decimal("500.00"), 1),
            ("Sushi Place", Decimal("105.00"), 3),
        ]
        sushi = flow.top_merchants[1]
        assert (sushi.category, sushi.group_id) == ("Dining Out", food_id)
        unlimited = compute_spending_flow(txs, lookup, months={1})
        assert "Refunder" not in {m.merchant for m in unlimited.top_merchants}


class TestComputeCategoryComparisons:
    def test_swing_against_trailing_average(self) -> None:
        food_id, _, lookup = _setup_groups()
        txs = [
            _row(month=1, amount="-40.00"),
            _row(month=2, amount="-60.00"),
            _row(month=3, amount="-100.00"),
            _row(month=3, category="Groceries", amount="-30.00"),
        ]

        comparisons = compute_category_comparisons(txs, lookup, 3)

        assert [(c.category, c.is_new) for c in comparisons] == [
            ("Groceries", True),
            ("Dining Out", False),
        ]
        dining = comparisons[1]
        assert (
            dining.group_id,
            dining.current_month_amount,
            dining.trailing_average,
        ) == (
            food_id,
            Decimal("100.00"),
            Decimal("50.00"),
        )
        assert (dining.delta_amount, dining.delta_percentage) == (
            Decimal("50.00"),
            Decimal(100),
        )

    def test_category_missing_this_month_still_compares(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [_row(month=1, amount="-40.00"), _row(month=2, category="Groceries")]
        by_category = {
            c.category: c for c in compute_category_comparisons(txs, lookup, 2)
        }
        assert by_category["Dining Out"].current_month_amount == Decimal(0)
        assert by_category["Dining Out"].delta_percentage == Decimal(-100)

    def test_uses_the_person_lens(self) -> None:
        _, _, lookup = _setup_groups()
        txs = [_row(month=1, amount="-100.00", payer=BOB.id, pct=50)]
        [alice] = compute_category_comparisons(txs, lookup, 1, person_id=ALICE.id)
        assert alice.current_month_amount == Decimal("50.00")

    def test_empty(self) -> None:
        _, _, lookup = _setup_groups()
        assert compute_category_comparisons([], lookup, 1) == []
