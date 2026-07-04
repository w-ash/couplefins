from datetime import UTC, date, datetime
from decimal import Decimal

from src.application.use_cases.get_dashboard import (
    GetDashboardCommand,
    GetDashboardUseCase,
    _resolve_active_month,
)
from src.application.use_cases.record_waived_settlement import (
    RecordWaivedSettlementCommand,
    RecordWaivedSettlementUseCase,
)
from src.domain.reconciliation import filter_split_transactions
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


def _make_command(
    year: int = 2026,
    month: int | None = 3,
) -> GetDashboardCommand:
    return GetDashboardCommand(year=year, month=month)


def _set_transactions(uow, txs):
    """Set both dashboard fetches from one list, mirroring the SQL filters:
    household rows for spending, settlement-relevant rows for balances."""
    uow.transactions.get_household_by_year.return_value = [
        tx for tx in txs if tx.household and not tx.is_settlement
    ]
    uow.transactions.get_settlement_relevant_by_date_range.return_value = (
        filter_split_transactions(txs)
    )


def _setup_uow_base(uow, alice, bob, *, groups=None, categories=None):
    uow.persons.get_all.return_value = [alice, bob]
    uow.category_groups.get_all.return_value = groups or []
    uow.categories.get_all.return_value = categories or []


async def test_happy_path_current_month() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    group = make_category_group(name="Food & Dining")
    category = make_category(name="Dining Out", group_id=group.id)
    _setup_uow_base(uow, alice, bob, groups=[group], categories=[category])

    txs = [
        make_transaction(
            date=date(2026, 3, 10),
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = [
        make_upload(person_id=alice.id),
        make_upload(person_id=bob.id),
    ]

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    assert result.current_month.start_date == date(2026, 3, 1)
    assert result.current_month.end_date == date(2026, 3, 31)
    assert result.current_month.total_household_spending == Decimal("100.00")
    assert result.current_month.transaction_count == 1
    assert all(s.has_uploaded for s in result.upload_statuses)


async def test_empty_month_zeroed_summary() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    _set_transactions(uow, [])
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    assert result.current_month.transaction_count == 0
    assert result.current_month.total_household_spending == Decimal(0)
    assert result.household_spending_ytd == Decimal(0)
    assert result.month_history == []


async def test_multi_month_history() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-60.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            date=date(2026, 2, 10),
            amount=Decimal("-80.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
        make_transaction(
            date=date(2026, 3, 5),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    assert len(result.month_history) == 3
    # Sorted newest first
    assert result.month_history[0].month == 3
    assert result.month_history[1].month == 2
    assert result.month_history[2].month == 1
    # Each month has correct spending
    assert result.month_history[0].total_household_spending == Decimal("100.00")
    assert result.month_history[1].total_household_spending == Decimal("80.00")
    assert result.month_history[2].total_household_spending == Decimal("60.00")


async def test_now_card_and_month_history_household_spending_agree() -> None:
    """A household no-split row (pct=100, e.g. concert tickets bought
    separately) plus a split row: the now-card's household_spending_month
    and the Month History figure for that same month must be one number,
    not two different 'household spending' metrics on the same page."""
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 3, 5),
            amount=Decimal("-60.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
            household=True,
        ),
        # Household, no split — e.g. concert tickets bought separately for a
        # show attended together. Dropped by reconcile()'s split-only total,
        # but it's still household spending.
        make_transaction(
            date=date(2026, 3, 12),
            amount=Decimal("-40.00"),
            payer_person_id=alice.id,
            payer_percentage=100,
            household=True,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    march_history = next(m for m in result.month_history if m.month == 3)
    assert result.household_spending_month == Decimal("100.00")
    assert march_history.total_household_spending == result.household_spending_month


async def test_month_with_only_spotted_rows_appears_in_history() -> None:
    """A month whose only activity is non-household split rows still shows
    in month history with its settlement balance."""
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 2, 10),
            amount=Decimal("-40.00"),
            payer_person_id=alice.id,
            payer_percentage=0,
            household=False,
            tags=("bob",),
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    assert len(result.month_history) == 1
    feb = result.month_history[0]
    assert feb.month == 2
    assert feb.total_household_spending == Decimal(0)
    assert feb.settlement_amount == Decimal("40.00")
    assert feb.settlement_from_person_id == bob.id
    assert feb.settlement_to_person_id == alice.id
    assert feb.is_settled is False


async def test_ytd_aggregates_across_months() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            date=date(2026, 2, 10),
            amount=Decimal("-60.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            date=date(2026, 3, 5),
            amount=Decimal("-40.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    # YTD = $100 + $60 + $40 = $200
    assert result.household_spending_ytd == Decimal("200.00")
    # YTD settlement: Alice paid $160, Bob paid $40. Each share = $100.
    # Alice overpaid by $60 → Bob owes Alice $60.
    assert result.ytd_settlement is not None
    assert result.ytd_settlement.amount == Decimal("60.00")
    assert result.ytd_settlement.from_person_id == bob.id
    assert result.ytd_settlement.to_person_id == alice.id


async def test_ytd_excludes_future_months() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        # April is after March (the requested month)
        make_transaction(
            date=date(2026, 4, 10),
            amount=Decimal("-200.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    # YTD should only include January, not April
    assert result.household_spending_ytd == Decimal("100.00")
    # Current month (March) should be empty
    assert result.current_month.transaction_count == 0


async def test_settlement_history_entries() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    jan_entry = result.month_history[-1]
    assert jan_entry.month == 1
    assert jan_entry.settlement_amount == Decimal("50.00")
    assert jan_entry.settlement_from_person_id == bob.id
    assert jan_entry.settlement_to_person_id == alice.id


async def test_personal_household_share_nets_refund() -> None:
    """A refund on a household split must reduce the personal share, not
    inflate it — mirrors the sign-aware fix in _compute_personal_spending."""
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 3, 10),
            amount=Decimal("-200.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
            household=True,
        ),
        make_transaction(
            date=date(2026, 3, 12),
            amount=Decimal("60.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
            household=True,
        ),
    ]
    uow.transactions.get_by_year.return_value = txs
    uow.transactions.get_settlement_relevant_by_date_range.return_value = (
        filter_split_transactions(txs)
    )
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []
    uow.category_group_budgets.get_by_year.return_value = []

    command = GetDashboardCommand(
        year=2026, month=3, scope="personal", person_id=alice.id
    )
    result = await GetDashboardUseCase().execute(command, uow)

    # Alice's share: $100 expense share - $30 refund share = $70
    assert result.my_household_share_month == Decimal("70.00")


# ─── Active month resolution ───


def test_resolve_active_month_picks_latest_unfinalized() -> None:
    by_month: dict[int, list] = {1: [], 2: [], 3: []}
    finalized = {1, 2}
    assert _resolve_active_month(by_month, finalized, fallback_month=4) == 3


def test_resolve_active_month_falls_back_to_latest_when_all_finalized() -> None:
    by_month: dict[int, list] = {1: [], 2: [], 3: []}
    finalized = {1, 2, 3}
    assert _resolve_active_month(by_month, finalized, fallback_month=4) == 3


def test_resolve_active_month_falls_back_to_current_when_no_txs() -> None:
    assert _resolve_active_month({}, set(), fallback_month=4) == 4


async def test_auto_month_picks_latest_unfinalized_with_txs() -> None:
    """The 'getting started' case: data exists but no reconciliations yet."""
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 2, 10),
            amount=Decimal("-80.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            date=date(2026, 3, 5),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    # No explicit month → auto-detect
    result = await GetDashboardUseCase().execute(_make_command(month=None), uow)

    # Should pick March (latest unfinalized with txs)
    assert result.current_month.start_date == date(2026, 3, 1)
    assert result.current_month.total_household_spending == Decimal("100.00")


async def test_auto_month_skips_finalized_months() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 2, 10),
            amount=Decimal("-80.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            date=date(2026, 3, 5),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []
    # March is finalized
    uow.reconciliation_periods.get_by_year.return_value = [
        make_reconciliation_period(year=2026, month=3, is_finalized=True),
    ]

    result = await GetDashboardUseCase().execute(_make_command(month=None), uow)

    # Should pick February (latest unfinalized with txs)
    assert result.current_month.start_date == date(2026, 2, 1)
    assert result.current_month.total_household_spending == Decimal("80.00")


# ─── Settlement status ───


async def test_month_with_full_settlement_is_settled() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    settled_at = datetime(2026, 2, 1, 12, 0, tzinfo=UTC)
    uow.settlements.get_by_year.return_value = [
        make_settlement(
            year=2026,
            month=1,
            amount=Decimal("50.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
            settled_at=settled_at,
        ),
    ]

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    jan = result.month_history[-1]
    assert jan.is_settled is True
    assert jan.settled_at == settled_at


async def test_month_with_partial_settlement_is_not_settled() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    uow.settlements.get_by_year.return_value = [
        make_settlement(
            year=2026,
            month=1,
            amount=Decimal("30.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
        ),
    ]

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    jan = result.month_history[-1]
    assert jan.is_settled is False
    assert jan.settled_at is None


async def test_multiple_settlements_summing_to_full() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-200.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    earlier = datetime(2026, 2, 1, 10, 0, tzinfo=UTC)
    later = datetime(2026, 2, 5, 14, 0, tzinfo=UTC)
    uow.settlements.get_by_year.return_value = [
        make_settlement(
            year=2026,
            month=1,
            amount=Decimal("60.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
            settled_at=earlier,
        ),
        make_settlement(
            year=2026,
            month=1,
            amount=Decimal("40.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
            settled_at=later,
        ),
    ]

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    jan = result.month_history[-1]
    assert jan.is_settled is True
    assert jan.settled_at == later


async def test_waived_settlement_counts_as_settled() -> None:
    """The waiver must be built via RecordWaivedSettlementUseCase rather than
    a hand-fabricated Settlement — a fabricated amount previously masked the
    v1.7.0 waiver no-op (the use case computing $0 and writing nothing)."""
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)
    set_passthrough_save(uow)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-10.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []
    uow.uploads.get_by_person_ids_with_transactions_in_date_range.return_value = []
    uow.persons.get_by_ids.return_value = [alice, bob]
    uow.settlements.get_by_period.return_value = []

    waive_result = await RecordWaivedSettlementUseCase().execute(
        RecordWaivedSettlementCommand(
            year=2026, month=1, from_person_id=bob.id, to_person_id=alice.id
        ),
        uow,
    )
    # Bob owes Alice 50% of $10 — the use case derives this from the same
    # transactions the dashboard reads, so it can't drift from a real write.
    assert waive_result.settlement.amount == Decimal("5.00")

    uow.settlements.get_by_year.return_value = [waive_result.settlement]

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    jan = result.month_history[-1]
    assert jan.is_settled is True


async def test_ytd_total_settled_accumulates_across_months() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            date=date(2026, 2, 10),
            amount=Decimal("-80.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    uow.settlements.get_by_year.return_value = [
        make_settlement(
            year=2026,
            month=1,
            amount=Decimal("50.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
        ),
        make_settlement(
            year=2026,
            month=2,
            amount=Decimal("40.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
        ),
    ]

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    assert result.ytd_total_settled == Decimal("90.00")


async def test_ytd_total_settled_excludes_future_months() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    uow.settlements.get_by_year.return_value = [
        make_settlement(
            year=2026,
            month=1,
            amount=Decimal("50.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
        ),
        make_settlement(
            year=2026,
            month=4,
            amount=Decimal("80.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
        ),
    ]

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    # Only January included (active month=3, April excluded)
    assert result.ytd_total_settled == Decimal("50.00")


async def test_zero_balance_month_is_trivially_settled() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    # Both pay equally → settlement amount = 0
    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            date=date(2026, 1, 20),
            amount=Decimal("-100.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    jan = result.month_history[-1]
    assert jan.settlement_amount == Decimal(0)
    assert jan.is_settled is True
    assert jan.settled_at is None


async def test_net_settlement_reflects_overpayment() -> None:
    """Dashboard should show net position after settlements, not gross."""
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    # Bob owes Alice $50, but pays $200 (overpayment)
    uow.settlements.get_by_year.return_value = [
        make_settlement(
            year=2026,
            month=1,
            amount=Decimal("200.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
        ),
    ]

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    # Month history: net reverses direction
    jan = result.month_history[-1]
    assert jan.is_settled is False
    assert jan.settlement_amount == Decimal("150.00")
    assert jan.settlement_from_person_id == alice.id  # Direction reversed
    assert jan.settlement_to_person_id == bob.id

    # Active month net settlement (January has no transactions in March context)
    # But YTD net should reflect the overpayment
    assert result.ytd_net_settlement is not None
    assert result.ytd_net_settlement.amount == Decimal("150.00")
    assert result.ytd_net_settlement.from_person_id == alice.id

    # Current month net (March has no transactions, no settlements)
    assert result.current_month_net_settlement is not None
    assert result.current_month_net_settlement.amount == Decimal(0)


async def test_net_settlement_partial_payment() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 3, 10),
            amount=Decimal("-200.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    _set_transactions(uow, txs)
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    uow.settlements.get_by_year.return_value = [
        make_settlement(
            year=2026,
            month=3,
            amount=Decimal("30.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
        ),
    ]

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    # Current month net: $100 gross - $30 paid = $70 remaining
    assert result.current_month_net_settlement is not None
    assert result.current_month_net_settlement.amount == Decimal("70.00")
    assert result.current_month_net_settlement.from_person_id == bob.id


async def test_no_settlements_yields_zero_ytd_total() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    _set_transactions(uow, [])
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    assert result.ytd_total_settled == Decimal(0)
