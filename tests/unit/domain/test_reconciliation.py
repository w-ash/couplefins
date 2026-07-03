from datetime import date
from decimal import Decimal
import uuid

import pytest

from src.domain.entities.category import Category
from src.domain.exceptions import InvariantViolationError
from src.domain.reconciliation import (
    PersonSummary,
    SettlementResult,
    _compute_settlement,
    compute_gross_settlement,
    compute_net_position,
    reconcile,
)
from tests.fixtures.factories import (
    make_category,
    make_category_group,
    make_person,
    make_settlement,
    make_transaction,
)


def _alice_bob() -> tuple:
    alice_id = uuid.uuid4()
    bob_id = uuid.uuid4()
    alice = make_person(id=alice_id, name="Alice")
    bob = make_person(id=bob_id, name="Bob")
    return alice, bob


def test_equal_split_both_paid_equally() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result.transaction_count == 2
    assert result.total_household_spending == Decimal("200.00")
    assert result.settlement is not None
    assert result.settlement.amount == Decimal(0)


def test_one_person_paid_everything() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            amount=Decimal("-60.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result.settlement is not None
    assert result.settlement.amount == Decimal("80.00")
    assert result.settlement.from_person_id == bob.id
    assert result.settlement.to_person_id == alice.id


def test_70_30_split() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=70,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result.settlement is not None
    # Alice paid 100, her share is 70. Bob's share is 30.
    # Bob owes Alice 30.
    assert result.settlement.amount == Decimal("30.00")
    assert result.settlement.from_person_id == bob.id
    assert result.settlement.to_person_id == alice.id


def test_mixed_splits() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            amount=Decimal("-200.00"),
            payer_person_id=bob.id,
            payer_percentage=70,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result.settlement is not None
    # Alice paid 100, share = 50 + 60 = 110 → net_owed = 10
    # Bob paid 200, share = 50 + 140 = 190 → net_owed = -10
    assert result.settlement.amount == Decimal("10.00")
    assert result.settlement.from_person_id == alice.id
    assert result.settlement.to_person_id == bob.id


def test_refund_reduces_settlement() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            amount=Decimal("20.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result.total_household_spending == Decimal("100.00")
    assert result.total_household_refunds == Decimal("20.00")
    assert result.net_household_spending == Decimal("80.00")
    assert result.settlement is not None
    # Expense: Alice paid 100, Alice share 50, Bob share 50 → Bob owes 50
    # Refund: Alice received 20, Alice share -10, Bob share -10 → Alice owes 10
    # Net: Bob owes 50 - 10 = 40
    assert result.settlement.amount == Decimal("40.00")
    assert result.settlement.from_person_id == bob.id


def test_100_0_split() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=100,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result.settlement is not None
    # Alice paid 100, her share is 100, Bob's share is 0.
    assert result.settlement.amount == Decimal(0)


def test_0_100_split() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=0,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result.settlement is not None
    # Alice paid 100, her share is 0, Bob's share is 100.
    # Bob owes Alice 100.
    assert result.settlement.amount == Decimal("100.00")
    assert result.settlement.from_person_id == bob.id
    assert result.settlement.to_person_id == alice.id


def test_empty_transactions() -> None:
    alice, bob = _alice_bob()

    result = reconcile(
        [],
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result.transaction_count == 0
    assert result.total_household_spending == Decimal(0)
    assert result.total_household_refunds == Decimal(0)
    assert result.net_household_spending == Decimal(0)
    assert result.settlement is not None
    assert result.settlement.amount == Decimal(0)
    assert result.category_group_breakdowns == []


def test_single_transaction() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result.transaction_count == 1
    assert result.total_household_spending == Decimal("50.00")
    assert result.settlement is not None
    assert result.settlement.amount == Decimal("25.00")
    assert result.settlement.from_person_id == bob.id


def test_category_group_aggregation() -> None:
    alice, bob = _alice_bob()
    group = make_category_group(name="Food & Dining")
    cat1 = make_category(name="Dining Out", group_id=group.id)
    cat2 = make_category(name="Groceries", group_id=group.id)

    txs = [
        make_transaction(
            category="Dining Out",
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal("-30.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [cat1, cat2],
        [group],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert len(result.category_group_breakdowns) == 1
    breakdown = result.category_group_breakdowns[0]
    assert breakdown.group_name == "Food & Dining"
    assert breakdown.total_amount == Decimal("80.00")
    assert breakdown.transaction_count == 2
    assert len(breakdown.categories) == 2
    # Sorted by amount desc
    assert breakdown.categories[0].category == "Dining Out"
    assert breakdown.categories[0].total_amount == Decimal("50.00")


def test_unmapped_category_becomes_uncategorized() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            category="Random Service",
            amount=Decimal("-25.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert len(result.category_group_breakdowns) == 1
    breakdown = result.category_group_breakdowns[0]
    assert breakdown.group_name == "Uncategorized"
    assert breakdown.group_id is None
    assert breakdown.categories[0].category == "Random Service"


def test_nullable_group_id_category_becomes_uncategorized() -> None:
    alice, bob = _alice_bob()
    group = make_category_group(name="Food & Dining")
    mapped = make_category(name="Groceries", group_id=group.id)
    unmapped = Category(id=uuid.uuid4(), name="New Thing", group_id=None)

    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            category="New Thing",
            amount=Decimal("-25.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [mapped, unmapped],
        [group],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert len(result.category_group_breakdowns) == 2
    food = next(
        b for b in result.category_group_breakdowns if b.group_name == "Food & Dining"
    )
    uncat = next(
        b for b in result.category_group_breakdowns if b.group_name == "Uncategorized"
    )
    assert food.total_amount == Decimal("50.00")
    assert uncat.total_amount == Decimal("25.00")
    assert uncat.group_id is None


def test_rounding_fractional_cents() -> None:
    alice, bob = _alice_bob()
    # $33.33 split 50/50 → payer rounds to 16.67, other gets remainder 16.66
    txs = [
        make_transaction(
            amount=Decimal("-33.33"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    alice_summary = next(s for s in result.person_summaries if s.person_id == alice.id)
    bob_summary = next(s for s in result.person_summaries if s.person_id == bob.id)
    assert alice_summary.total_share == Decimal("16.67")
    assert bob_summary.total_share == Decimal("16.66")
    assert alice_summary.total_share + bob_summary.total_share == Decimal("33.33")


def test_all_refunds_no_expenses() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("50.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            amount=Decimal("30.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result.total_household_spending == Decimal(0)
    assert result.total_household_refunds == Decimal("80.00")
    assert result.net_household_spending == Decimal("-80.00")
    assert result.settlement is not None
    # Alice received 50, share -25. Bob received 30, share -15.
    # Alice: paid -50, share -25 → net = -25 + 50 = 25... let me think.
    # Refund: paid[alice] -= 50, share[alice] -= 25, share[bob] -= 25
    # Refund: paid[bob] -= 30, share[bob] -= 15, share[alice] -= 15
    # Alice: paid=-50, share=-40. net = -40 - (-50) = 10. Alice owes 10.
    # Bob: paid=-30, share=-40. net = -40 - (-30) = -10. Bob is owed 10.
    assert result.settlement.amount == Decimal("10.00")
    assert result.settlement.from_person_id == alice.id
    assert result.settlement.to_person_id == bob.id


def test_personal_transactions_excluded() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
            tags=("shared",),
        ),
        make_transaction(
            amount=Decimal("-200.00"),
            payer_person_id=alice.id,
            payer_percentage=100,
            household=False,
            tags=(),
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result.transaction_count == 1
    assert result.total_household_spending == Decimal("100.00")


def test_excluded_transactions_not_in_settlement() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
            is_excluded=True,
        ),
        make_transaction(
            amount=Decimal("-60.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result.transaction_count == 1
    assert result.total_household_spending == Decimal("60.00")


def test_settlement_transactions_not_in_reconciliation() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
            is_settlement=True,
        ),
        make_transaction(
            amount=Decimal("-60.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
    ]

    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result.transaction_count == 1
    assert result.total_household_spending == Decimal("60.00")


# --- compute_net_position tests ---


def test_net_position_no_settlements_returns_gross() -> None:
    alice, bob = _alice_bob()
    gross = SettlementResult(
        amount=Decimal("100.00"), from_person_id=alice.id, to_person_id=bob.id
    )
    result = compute_net_position(gross, [])
    assert result is gross


def test_net_position_gross_none_returns_none() -> None:
    assert compute_net_position(None, []) is None


def test_net_position_partial_payment() -> None:
    alice, bob = _alice_bob()
    gross = SettlementResult(
        amount=Decimal("200.00"), from_person_id=alice.id, to_person_id=bob.id
    )
    settlement = make_settlement(
        amount=Decimal("50.00"), from_person_id=alice.id, to_person_id=bob.id
    )
    result = compute_net_position(gross, [settlement])
    assert result is not None
    assert result.amount == Decimal("150.00")
    assert result.from_person_id == alice.id
    assert result.to_person_id == bob.id


def test_net_position_exact_payment_returns_none() -> None:
    alice, bob = _alice_bob()
    gross = SettlementResult(
        amount=Decimal("212.65"), from_person_id=alice.id, to_person_id=bob.id
    )
    settlement = make_settlement(
        amount=Decimal("212.65"), from_person_id=alice.id, to_person_id=bob.id
    )
    assert compute_net_position(gross, [settlement]) is None


def test_net_position_overpayment_reverses_direction() -> None:
    alice, bob = _alice_bob()
    gross = SettlementResult(
        amount=Decimal("212.65"), from_person_id=alice.id, to_person_id=bob.id
    )
    settlement = make_settlement(
        amount=Decimal("1981.00"), from_person_id=alice.id, to_person_id=bob.id
    )
    result = compute_net_position(gross, [settlement])
    assert result is not None
    assert result.amount == Decimal("1768.35")
    assert result.from_person_id == bob.id
    assert result.to_person_id == alice.id


def test_net_position_multiple_settlements() -> None:
    alice, bob = _alice_bob()
    gross = SettlementResult(
        amount=Decimal("300.00"), from_person_id=alice.id, to_person_id=bob.id
    )
    s1 = make_settlement(
        amount=Decimal("100.00"), from_person_id=alice.id, to_person_id=bob.id
    )
    s2 = make_settlement(
        amount=Decimal("50.00"), from_person_id=alice.id, to_person_id=bob.id
    )
    result = compute_net_position(gross, [s1, s2])
    assert result is not None
    assert result.amount == Decimal("150.00")
    assert result.from_person_id == alice.id


# --- zero-sum invariant tests ---


def test_mixed_odd_cent_amounts_pass_zero_sum() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-33.33"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            amount=Decimal("-17.51"),
            payer_person_id=bob.id,
            payer_percentage=70,
        ),
        make_transaction(
            amount=Decimal("-9.99"),
            payer_person_id=alice.id,
            payer_percentage=30,
        ),
    ]

    # Should complete without InvariantViolationError
    result = reconcile(
        txs,
        [alice, bob],
        [],
        [],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )
    assert result.settlement is not None


def test_broken_summaries_raise_invariant_violation() -> None:
    alice, bob = _alice_bob()
    # Artificially broken: net1 + net2 != 0
    summaries = [
        PersonSummary(
            person_id=alice.id, total_paid=Decimal(100), total_share=Decimal(60)
        ),
        PersonSummary(person_id=bob.id, total_paid=Decimal(0), total_share=Decimal(50)),
    ]
    with pytest.raises(InvariantViolationError, match="Zero-sum invariant violated"):
        _compute_settlement(summaries)


def test_compute_gross_settlement_ignores_household_flag() -> None:
    alice, bob = _alice_bob()
    txs = [
        # Shared household expense: Bob owes Alice $50
        make_transaction(
            amount=Decimal("-100.00"), payer_person_id=alice.id, payer_percentage=50
        ),
        # Spotted (household=false): Bob owes Alice $40
        make_transaction(
            amount=Decimal("-40.00"),
            payer_person_id=alice.id,
            payer_percentage=0,
            household=False,
            tags=("bob",),
        ),
        # Non-participants: household no-split, excluded, settlement transfer
        make_transaction(
            amount=Decimal("-500.00"), payer_person_id=bob.id, payer_percentage=100
        ),
        make_transaction(
            amount=Decimal("-30.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
            is_excluded=True,
        ),
        make_transaction(
            amount=Decimal("-90.00"),
            payer_person_id=bob.id,
            payer_percentage=0,
            is_settlement=True,
            household=False,
        ),
    ]

    result = compute_gross_settlement(txs, [alice.id, bob.id])

    assert result is not None
    assert result.amount == Decimal("90.00")
    assert result.from_person_id == bob.id
    assert result.to_person_id == alice.id


def test_compute_gross_settlement_empty_is_zero_amount() -> None:
    alice, bob = _alice_bob()
    result = compute_gross_settlement([], [alice.id, bob.id])
    assert result is not None
    assert result.amount == Decimal(0)
