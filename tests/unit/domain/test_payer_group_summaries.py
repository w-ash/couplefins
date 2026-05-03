from decimal import Decimal
import uuid

from src.domain.categories import build_category_lookup
from src.domain.reconciliation import (
    compute_payer_group_summaries,
    compute_payer_split_summaries,
    filter_split_transactions,
)
from tests.fixtures.factories import (
    make_category,
    make_category_group,
    make_person,
    make_transaction,
)


def _alice_bob() -> tuple:
    alice = make_person(id=uuid.uuid4(), name="Alice")
    bob = make_person(id=uuid.uuid4(), name="Bob")
    return alice, bob


def test_two_payers_same_group() -> None:
    alice, bob = _alice_bob()
    group = make_category_group(name="Food & Dining")
    cat = make_category(name="Dining Out", group_id=group.id)
    lookup = build_category_lookup([cat], [group])

    txs = filter_split_transactions([
        make_transaction(
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            category="Dining Out",
            amount=Decimal("-40.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
    ])

    rows = compute_payer_group_summaries(txs, [alice.id, bob.id], lookup)

    assert len(rows) == 2
    by_payer = {r.payer_person_id: r for r in rows}
    alice_row = by_payer[alice.id]
    bob_row = by_payer[bob.id]

    assert alice_row.group_name == "Food & Dining"
    assert alice_row.total_paid == Decimal("100.00")
    assert alice_row.total_share == Decimal("50.00")
    assert alice_row.transaction_count == 1

    assert bob_row.total_paid == Decimal("40.00")
    assert bob_row.total_share == Decimal("20.00")
    assert bob_row.transaction_count == 1


def test_refund_reduces_paid_and_share() -> None:
    alice, bob = _alice_bob()
    group = make_category_group(name="Shopping")
    cat = make_category(name="Clothing", group_id=group.id)
    lookup = build_category_lookup([cat], [group])

    txs = filter_split_transactions([
        make_transaction(
            category="Clothing",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            category="Clothing",
            amount=Decimal("30.00"),  # refund
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ])

    rows = compute_payer_group_summaries(txs, [alice.id, bob.id], lookup)

    assert len(rows) == 1  # only Alice paid
    row = rows[0]
    assert row.payer_person_id == alice.id
    assert row.total_paid == Decimal("70.00")  # 100 - 30
    assert row.total_share == Decimal("35.00")  # 50 - 15
    assert row.transaction_count == 2


def test_unmapped_category_is_uncategorized() -> None:
    alice, bob = _alice_bob()
    lookup: dict[str, tuple[uuid.UUID, str]] = {}

    txs = filter_split_transactions([
        make_transaction(
            category="Random Service",
            amount=Decimal("-25.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ])

    rows = compute_payer_group_summaries(txs, [alice.id, bob.id], lookup)

    assert len(rows) == 1
    assert rows[0].group_id is None
    assert rows[0].group_name == "Uncategorized"


def test_payer_percentage_100_filtered_out() -> None:
    alice, _bob = _alice_bob()
    txs = filter_split_transactions([
        make_transaction(
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
            payer_percentage=100,
        ),
    ])

    assert txs == []


def test_excluded_and_settlement_filtered_out() -> None:
    alice, _bob = _alice_bob()
    txs = filter_split_transactions([
        make_transaction(
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
            is_excluded=True,
        ),
        make_transaction(
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
            is_settlement=True,
        ),
    ])

    assert txs == []


def test_multi_group_ordering_descending_with_uncategorized_last() -> None:
    alice, bob = _alice_bob()
    food = make_category_group(name="Food & Dining")
    travel = make_category_group(name="Travel")
    food_cat = make_category(name="Dining Out", group_id=food.id)
    travel_cat = make_category(name="Flights", group_id=travel.id)
    lookup = build_category_lookup([food_cat, travel_cat], [food, travel])

    txs = filter_split_transactions([
        # Travel: $300 (largest) - sorted first
        make_transaction(
            category="Flights",
            amount=Decimal("-300.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        # Food: $100 - sorted second
        make_transaction(
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
        # Uncategorized: $200 - sorted last despite being larger than food
        make_transaction(
            category="Random",
            amount=Decimal("-200.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ])

    rows = compute_payer_group_summaries(txs, [alice.id, bob.id], lookup)

    assert [r.group_name for r in rows] == ["Travel", "Food & Dining", "Uncategorized"]


def test_within_group_payer_index_order_preserved() -> None:
    alice, bob = _alice_bob()
    group = make_category_group(name="Food & Dining")
    cat = make_category(name="Dining Out", group_id=group.id)
    lookup = build_category_lookup([cat], [group])

    txs = filter_split_transactions([
        make_transaction(
            category="Dining Out",
            amount=Decimal("-50.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
        make_transaction(
            category="Dining Out",
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ])

    rows = compute_payer_group_summaries(txs, [alice.id, bob.id], lookup)

    # person_ids order is [alice, bob] → Alice's row first within the group.
    assert rows[0].payer_person_id == alice.id
    assert rows[1].payer_person_id == bob.id


def test_payer_split_summaries_per_payer_aggregate() -> None:
    alice, bob = _alice_bob()
    txs = filter_split_transactions([
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            amount=Decimal("-30.00"),
            payer_person_id=alice.id,
            payer_percentage=70,
        ),
        make_transaction(
            amount=Decimal("-40.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
    ])

    rows = compute_payer_split_summaries(txs, [alice.id, bob.id])

    assert len(rows) == 2
    assert rows[0].payer_person_id == alice.id
    assert rows[0].total_paid == Decimal("130.00")  # 100 + 30
    assert rows[0].total_share == Decimal("71.00")  # 50 + 21
    assert rows[0].transaction_count == 2

    assert rows[1].payer_person_id == bob.id
    assert rows[1].total_paid == Decimal("40.00")
    assert rows[1].total_share == Decimal("20.00")
    assert rows[1].transaction_count == 1


def test_payer_split_summaries_zero_for_inactive_payer() -> None:
    alice, bob = _alice_bob()
    txs = filter_split_transactions([
        make_transaction(
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ])

    rows = compute_payer_split_summaries(txs, [alice.id, bob.id])

    assert len(rows) == 2
    bob_row = next(r for r in rows if r.payer_person_id == bob.id)
    assert bob_row.total_paid == Decimal(0)
    assert bob_row.total_share == Decimal(0)
    assert bob_row.transaction_count == 0


def test_partner_share_only_cell_does_not_emit_row() -> None:
    """If Alice spotted Bob (0/100) on a category Bob never paid in, only one row emits."""
    alice, bob = _alice_bob()
    group = make_category_group(name="Auto & Transport")
    cat = make_category(name="Parking", group_id=group.id)
    lookup = build_category_lookup([cat], [group])

    txs = filter_split_transactions([
        make_transaction(
            category="Parking",
            amount=Decimal("-30.00"),
            payer_person_id=alice.id,
            payer_percentage=0,  # Alice paid 0, Bob owes 100% (spotted)
        ),
    ])

    rows = compute_payer_group_summaries(txs, [alice.id, bob.id], lookup)

    # Only Alice's row emits — she fronted the bill. Bob has share only,
    # which is captured in Alice's row's partner-share derivation
    # (paid - share = 30 - 0 = 30 owed back by Bob).
    assert len(rows) == 1
    assert rows[0].payer_person_id == alice.id
    assert rows[0].total_paid == Decimal("30.00")
    assert rows[0].total_share == Decimal("0.00")
    assert rows[0].transaction_count == 1
