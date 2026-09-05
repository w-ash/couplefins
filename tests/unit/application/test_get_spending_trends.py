from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from src.application.use_cases.get_spending_trends import (
    GetSpendingTrendsCommand,
    GetSpendingTrendsUseCase,
)
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import ValidationError
from tests.fixtures.factories import (
    make_category,
    make_category_group,
    make_category_group_budget,
    make_person,
    make_settlement,
    make_transaction,
    make_transfer_group,
)
from tests.fixtures.mocks import make_mock_uow


def _setup_uow():
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    uow.persons.get_all.return_value = [alice, bob]

    food_group = make_category_group(name="Food & Dining")
    uow.category_groups.get_all.return_value = [food_group]

    category = make_category(name="Dining Out", group_id=food_group.id)
    uow.categories.get_all.return_value = [category]

    uow.category_group_budgets.get_by_month.return_value = []
    uow.category_group_budgets.get_by_year.return_value = []

    return uow, alice, bob, food_group


async def test_happy_path() -> None:
    uow, alice, _, food_group = _setup_uow()
    uow.transactions.get_household_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-80.00"),
            payer_person_id=alice.id,
        ),
        make_transaction(
            date=date(2026, 2, 5),
            category="Dining Out",
            amount=Decimal("-60.00"),
            payer_person_id=alice.id,
        ),
    ]

    # Pin the month explicitly — the YTD total is now bounded at the
    # selected month, so leaving this to the real-clock default would make
    # the assertion depend on what month the test happens to run in.
    command = GetSpendingTrendsCommand(year=2026, month=2)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.year == 2026
    assert len(result.trends.monthly_group_spending) == 2
    assert len(result.trends.monthly_totals) == 2
    assert len(result.trends.group_summaries) == 1
    assert result.trends.group_summaries[0].group_id == food_group.id
    assert result.trends.group_summaries[0].ytd_total == Decimal("140.00")


async def test_ytd_bounded_at_selected_month() -> None:
    """Viewing an earlier month must not pull in later months' spending —
    matches Budget/Dashboard's YTD, which is always bounded at the
    selected month."""
    uow, alice, _, _food_group = _setup_uow()
    uow.transactions.get_household_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-80.00"),
            payer_person_id=alice.id,
        ),
        make_transaction(
            date=date(2026, 2, 5),
            category="Dining Out",
            amount=Decimal("-60.00"),
            payer_person_id=alice.id,
        ),
        make_transaction(
            date=date(2026, 3, 5),
            category="Dining Out",
            amount=Decimal("-1000.00"),
            payer_person_id=alice.id,
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026, month=2)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    # Per-month lists still cover the whole year (sparklines want the shape)...
    assert len(result.trends.monthly_totals) == 3
    # ...but the YTD total is bounded through February.
    assert result.trends.group_summaries[0].ytd_total == Decimal("140.00")


async def test_no_data() -> None:
    uow, _, _, _ = _setup_uow()
    uow.transactions.get_household_by_year.return_value = []

    command = GetSpendingTrendsCommand(year=2026)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.year == 2026
    assert result.trends.monthly_group_spending == []
    assert result.trends.monthly_totals == []
    assert result.trends.group_summaries == []
    assert result.comparison_cards == []
    assert result.budget_lines == {}
    assert result.settlement_trend == []


def test_invalid_year() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        GetSpendingTrendsCommand(year=0)


def test_invalid_month() -> None:
    with pytest.raises(ValueError, match="must be 1-12"):
        GetSpendingTrendsCommand(year=2026, month=13)


async def test_comparison_cards_computed() -> None:
    uow, alice, _, food_group = _setup_uow()
    uow.transactions.get_household_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
        ),
        make_transaction(
            date=date(2026, 2, 10),
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
        ),
        make_transaction(
            date=date(2026, 3, 10),
            category="Dining Out",
            amount=Decimal("-200.00"),
            payer_person_id=alice.id,
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026, month=3)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.month == 3
    assert len(result.comparison_cards) == 1
    card = result.comparison_cards[0]
    assert card.group_id == food_group.id
    assert card.current_month_amount == Decimal("200.00")
    assert card.trailing_average == Decimal("100.00")


async def test_budget_lines_populated() -> None:
    uow, alice, _, food_group = _setup_uow()
    uow.transactions.get_household_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
        ),
    ]
    uow.category_group_budgets.get_by_year.return_value = [
        make_category_group_budget(
            group_id=food_group.id,
            monthly_amount=Decimal("500.00"),
            year=2026,
            month=1,
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026, month=1)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert food_group.id in result.budget_lines
    assert result.budget_lines[food_group.id] == {1: Decimal("500.00")}


async def test_budget_lines_empty_when_no_budgets() -> None:
    uow, _, _, _ = _setup_uow()
    uow.transactions.get_household_by_year.return_value = []

    command = GetSpendingTrendsCommand(year=2026, month=1)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.budget_lines == {}


async def test_budget_lines_per_month() -> None:
    uow, alice, _, food_group = _setup_uow()
    uow.transactions.get_household_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
        ),
    ]
    uow.category_group_budgets.get_by_year.return_value = [
        make_category_group_budget(
            group_id=food_group.id,
            monthly_amount=Decimal("500.00"),
            year=2026,
            month=1,
        ),
        make_category_group_budget(
            group_id=food_group.id,
            monthly_amount=Decimal("600.00"),
            year=2026,
            month=2,
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026, month=2)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.budget_lines[food_group.id] == {
        1: Decimal("500.00"),
        2: Decimal("600.00"),
    }


async def test_budget_lines_sparse_months() -> None:
    uow, alice, _, food_group = _setup_uow()
    uow.transactions.get_household_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
        ),
    ]
    uow.category_group_budgets.get_by_year.return_value = [
        make_category_group_budget(
            group_id=food_group.id,
            monthly_amount=Decimal("500.00"),
            year=2026,
            month=1,
        ),
        make_category_group_budget(
            group_id=food_group.id,
            monthly_amount=Decimal("500.00"),
            year=2026,
            month=3,
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026, month=3)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    months = result.budget_lines[food_group.id]
    assert 1 in months
    assert 2 not in months  # null semantics: absent, not 0
    assert 3 in months


async def test_settlement_trend_populated() -> None:
    uow, alice, _bob, _food_group = _setup_uow()
    txs = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
        ),
        make_transaction(
            date=date(2026, 2, 10),
            category="Dining Out",
            amount=Decimal("-80.00"),
            payer_person_id=alice.id,
        ),
    ]
    uow.transactions.get_household_by_year.return_value = txs
    # The settlement trend is computed over settlement-relevant rows (ledger).
    uow.transactions.get_all_settlement_relevant.return_value = txs

    command = GetSpendingTrendsCommand(year=2026, month=2)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert len(result.settlement_trend) == 2
    jan = result.settlement_trend[0]
    assert jan.month == 1
    assert jan.amount > 0
    assert jan.is_settled is False
    assert jan.status == "carried_forward"


async def test_settlement_trend_marks_settled() -> None:
    uow, alice, bob, _food_group = _setup_uow()
    txs = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
        ),
    ]
    uow.transactions.get_household_by_year.return_value = txs
    uow.transactions.get_all_settlement_relevant.return_value = txs
    # Settlement that covers the owed amount
    uow.settlements.get_all.return_value = [
        make_settlement(
            amount=Decimal("50.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
            settled_at=datetime(2026, 1, 31, tzinfo=UTC),
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026, month=1)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert len(result.settlement_trend) == 1
    assert result.settlement_trend[0].is_settled is True
    assert result.settlement_trend[0].status == "settled"


async def test_settlement_trend_reverse_direction_not_settled() -> None:
    uow, alice, bob, _food_group = _setup_uow()
    txs = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
        ),
    ]
    uow.transactions.get_household_by_year.return_value = txs
    uow.transactions.get_all_settlement_relevant.return_value = txs
    # Gross: bob owes alice $50. A same-magnitude payment in the *wrong*
    # direction (alice paying bob) doubles the imbalance instead of
    # clearing it — must not be marked settled.
    uow.settlements.get_all.return_value = [
        make_settlement(
            amount=Decimal("50.00"),
            from_person_id=alice.id,
            to_person_id=bob.id,
            settled_at=datetime(2026, 1, 31, tzinfo=UTC),
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026, month=1)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert len(result.settlement_trend) == 1
    assert result.settlement_trend[0].is_settled is False


async def test_settlement_trend_includes_non_household_month() -> None:
    uow, alice, _bob, _food_group = _setup_uow()
    # A month whose only settlement signal is a spotted (non-household) row must
    # still appear — gross runs over settlement-relevant rows, not household-only.
    spotted = make_transaction(
        date=date(2026, 3, 10),
        category="Dining Out",
        amount=Decimal("-30.00"),
        payer_person_id=alice.id,
        household=False,
        payer_percentage=0,
    )
    uow.transactions.get_household_by_year.return_value = []
    uow.transactions.get_all_settlement_relevant.return_value = [spotted]

    command = GetSpendingTrendsCommand(year=2026, month=3)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert len(result.settlement_trend) == 1
    assert result.settlement_trend[0].month == 3
    assert result.settlement_trend[0].amount == Decimal("30.00")


async def test_past_year_ytd_spans_full_year() -> None:
    uow, alice, _bob, _food_group = _setup_uow()
    # A completed past year with no month specified includes spend from every
    # month in the YTD summaries — not just up to the current calendar month.
    txs = [
        make_transaction(
            date=date(2000, 1, 10),
            category="Dining Out",
            amount=Decimal("-40.00"),
            payer_person_id=alice.id,
        ),
        make_transaction(
            date=date(2000, 11, 10),
            category="Dining Out",
            amount=Decimal("-60.00"),
            payer_person_id=alice.id,
        ),
    ]
    uow.transactions.get_household_by_year.return_value = txs
    uow.transactions.get_settlement_relevant_by_date_range.return_value = txs

    command = GetSpendingTrendsCommand(year=2000)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.trends.group_summaries[0].ytd_total == Decimal("100.00")


async def test_persons_included() -> None:
    uow, _alice, _bob, _ = _setup_uow()
    uow.transactions.get_household_by_year.return_value = []

    command = GetSpendingTrendsCommand(year=2026)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert len(result.persons) == 2
    names = {p.name for p in result.persons}
    assert names == {"Alice", "Bob"}


async def test_comparison_year_returns_both_years() -> None:
    uow, alice, _, _food_group = _setup_uow()

    current_txs = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-80.00"),
            payer_person_id=alice.id,
        ),
    ]
    comparison_txs = [
        make_transaction(
            date=date(2025, 1, 10),
            category="Dining Out",
            amount=Decimal("-60.00"),
            payer_person_id=alice.id,
        ),
    ]

    uow.transactions.get_household_by_year.side_effect = lambda year: (
        current_txs if year == 2026 else comparison_txs
    )

    command = GetSpendingTrendsCommand(year=2026, comparison_year=2025)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert len(result.trends.monthly_group_spending) == 1
    assert result.trends.monthly_group_spending[0].amount == Decimal("80.00")

    assert len(result.comparison_monthly_group_spending) == 1
    assert result.comparison_monthly_group_spending[0].year == 2025
    assert result.comparison_monthly_group_spending[0].amount == Decimal("60.00")


async def test_comparison_year_none_returns_empty() -> None:
    uow, alice, _, _ = _setup_uow()
    uow.transactions.get_household_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
        ),
    ]

    command = GetSpendingTrendsCommand(year=2026)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.comparison_monthly_group_spending == []


async def test_comparison_year_no_data() -> None:
    uow, alice, _, _ = _setup_uow()
    uow.transactions.get_household_by_year.side_effect = lambda year: (
        [
            make_transaction(
                date=date(2026, 1, 10),
                category="Dining Out",
                amount=Decimal("-50.00"),
                payer_person_id=alice.id,
            ),
        ]
        if year == 2026
        else []
    )

    command = GetSpendingTrendsCommand(year=2026, comparison_year=2025)
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    assert result.comparison_monthly_group_spending == []


def test_invalid_comparison_year() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        GetSpendingTrendsCommand(year=2026, comparison_year=0)


# --- personal scope ---


def test_personal_scope_requires_person_id() -> None:
    with pytest.raises(ValidationError, match="person_id is required"):
        GetSpendingTrendsCommand(year=2026, scope="personal")


async def test_personal_scope_reads_all_rows_and_own_budgets() -> None:
    """Personal scope must take the whole year (personal and spotted rows
    live outside the household fetch) and overlay the person's own budgets."""
    uow, alice, bob, food_group = _setup_uow()
    uow.transactions.get_by_year.return_value = [
        make_transaction(
            date=date(2026, 1, 10),
            category="Dining Out",
            amount=Decimal("-80.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            date=date(2026, 1, 12),
            category="Dining Out",
            amount=Decimal("-30.00"),
            payer_person_id=bob.id,
            payer_percentage=0,
            household=False,
            tags=("alice",),
        ),
        make_transaction(
            date=date(2026, 1, 14),
            category="Dining Out",
            amount=Decimal("-99.00"),
            payer_person_id=bob.id,
            payer_percentage=100,
            household=False,
            tags=(),
        ),
    ]

    command = GetSpendingTrendsCommand(
        year=2026, month=1, scope="personal", person_id=alice.id
    )
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    uow.transactions.get_household_by_year.assert_not_called()
    uow.category_group_budgets.get_by_year.assert_called_once_with(2026, alice.id)
    # The hidden "Who's paying" section costs an all-time ledger load — skipped.
    uow.settlements.get_all.assert_not_called()
    assert result.settlement_trend == []
    assert result.monthly_person_paid == []
    # Alice's half of dinner + Bob's spot for her; Bob's own row excluded.
    assert result.trends.group_summaries[0].group_id == food_group.id
    assert result.trends.group_summaries[0].ytd_total == Decimal("70.00")


async def test_personal_scope_comparison_year_uses_same_lens() -> None:
    uow, alice, _, _food_group = _setup_uow()
    uow.transactions.get_by_year.side_effect = lambda year: [
        make_transaction(
            date=date(year, 3, 10),
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        )
    ]

    command = GetSpendingTrendsCommand(
        year=2026, month=3, scope="personal", person_id=alice.id, comparison_year=2025
    )
    result = await GetSpendingTrendsUseCase().execute(command, uow)

    uow.transactions.get_household_by_year.assert_not_called()
    assert result.comparison_monthly_group_spending[0].amount == Decimal("50.00")


async def test_household_scope_fetches_household_rows_and_budgets() -> None:
    uow, _, _, _food_group = _setup_uow()
    uow.transactions.get_household_by_year.return_value = []

    result = await GetSpendingTrendsUseCase().execute(
        GetSpendingTrendsCommand(year=2026, month=1), uow
    )

    uow.transactions.get_by_year.assert_not_called()
    uow.category_group_budgets.get_by_year.assert_called_once_with(2026, None)
    assert result.settlement_trend == []


async def test_transfer_rows_excluded_in_both_scopes_and_comparison_year() -> None:
    uow, alice, _, food_group = _setup_uow()
    transfer, card_payment = make_transfer_group()
    uow.category_groups.get_all.return_value = [food_group, transfer]
    uow.categories.get_all.return_value = [
        make_category(name="Dining Out", group_id=food_group.id),
        card_payment,
    ]

    def rows(year: int) -> list[Transaction]:
        return [
            make_transaction(
                date=date(year, 1, 10),
                category="Dining Out",
                amount=Decimal("-80.00"),
                payer_person_id=alice.id,
            ),
            make_transaction(
                date=date(year, 1, 12),
                category="Credit Card Payment",
                amount=Decimal("-3000.00"),
                payer_person_id=alice.id,
                payer_percentage=100,
                household=False,
                tags=(),
            ),
        ]

    uow.transactions.get_by_year.side_effect = rows
    uow.transactions.get_household_by_year.side_effect = rows

    for scope, person_id, expected in (
        ("household", None, Decimal("80.00")),
        ("personal", alice.id, Decimal("40.00")),
    ):
        result = await GetSpendingTrendsUseCase().execute(
            GetSpendingTrendsCommand(
                year=2026,
                month=1,
                scope=scope,
                person_id=person_id,
                comparison_year=2025,
            ),
            uow,
        )
        assert [g.group_id for g in result.trends.group_summaries] == [food_group.id]
        assert result.trends.group_summaries[0].ytd_total == expected
        assert [m.amount for m in result.comparison_monthly_group_spending] == [
            expected
        ]
