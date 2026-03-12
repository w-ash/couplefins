from datetime import date
from decimal import Decimal
import uuid

from src.domain.export.adjustments import compute_adjustments
from tests.fixtures.factories import make_person, make_transaction


def _alice_bob() -> tuple:
    alice = make_person(name="Alice", adjustment_account="Alice Adjustments")
    bob = make_person(name="Bob", adjustment_account="Bob Adjustments")
    return alice, bob


def test_50_50_expense_payer_gets_credit() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        )
    ]

    alice_adj = compute_adjustments(txs, alice)
    assert len(alice_adj) == 1
    assert alice_adj[0].amount == Decimal("50.00")  # credit for Bob's share

    bob_adj = compute_adjustments(txs, bob)
    assert len(bob_adj) == 1
    assert bob_adj[0].amount == Decimal("-50.00")  # debit for Bob's share


def test_70_30_split() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=70,
        )
    ]

    alice_adj = compute_adjustments(txs, alice)
    assert alice_adj[0].amount == Decimal("30.00")  # Bob owes 30%

    bob_adj = compute_adjustments(txs, bob)
    assert bob_adj[0].amount == Decimal("-30.00")  # Bob owes 30%


def test_100_0_split_skips_zero_share() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=100,
        )
    ]

    alice_adj = compute_adjustments(txs, alice)
    assert alice_adj == []

    bob_adj = compute_adjustments(txs, bob)
    assert bob_adj == []


def test_0_100_split_full_amount() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=0,
        )
    ]

    alice_adj = compute_adjustments(txs, alice)
    assert alice_adj[0].amount == Decimal("100.00")

    bob_adj = compute_adjustments(txs, bob)
    assert bob_adj[0].amount == Decimal("-100.00")


def test_refund_inverts_signs() -> None:
    alice, bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("20.00"),  # refund
            payer_person_id=alice.id,
            payer_percentage=50,
        )
    ]

    alice_adj = compute_adjustments(txs, alice)
    assert alice_adj[0].amount == Decimal("-10.00")  # payer gets debit for refund

    bob_adj = compute_adjustments(txs, bob)
    assert bob_adj[0].amount == Decimal("10.00")  # non-payer gets credit for refund


def test_dedup_ids_are_deterministic() -> None:
    alice, _bob = _alice_bob()
    tx_id = uuid.uuid4()
    txs = [
        make_transaction(id=tx_id, amount=Decimal("-100.00"), payer_person_id=alice.id)
    ]

    first = compute_adjustments(txs, alice)
    second = compute_adjustments(txs, alice)
    assert first[0].dedup_id == second[0].dedup_id


def test_dedup_ids_differ_per_person() -> None:
    alice, bob = _alice_bob()
    tx_id = uuid.uuid4()
    txs = [
        make_transaction(id=tx_id, amount=Decimal("-100.00"), payer_person_id=alice.id)
    ]

    alice_adj = compute_adjustments(txs, alice)
    bob_adj = compute_adjustments(txs, bob)
    assert alice_adj[0].dedup_id != bob_adj[0].dedup_id


def test_empty_transactions() -> None:
    alice, _bob = _alice_bob()
    assert compute_adjustments([], alice) == []


def test_rounding_fractional_cents() -> None:
    alice, _bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-33.33"),
            payer_person_id=alice.id,
            payer_percentage=50,
        )
    ]

    adj = compute_adjustments(txs, alice)
    # 33.33 * 50/100 = 16.665 → 16.67 (ROUND_HALF_UP)
    assert adj[0].amount == Decimal("16.67")


def test_deterministic_sort_order() -> None:
    alice, _bob = _alice_bob()
    txs = [
        make_transaction(
            date=date(2026, 1, 20),
            merchant="Zebra",
            amount=Decimal("-10.00"),
            payer_person_id=alice.id,
        ),
        make_transaction(
            date=date(2026, 1, 10),
            merchant="Apple",
            amount=Decimal("-20.00"),
            payer_person_id=alice.id,
        ),
        make_transaction(
            date=date(2026, 1, 10),
            merchant="Apple",
            category="Groceries",
            amount=Decimal("-15.00"),
            payer_person_id=alice.id,
        ),
    ]

    adj = compute_adjustments(txs, alice)
    assert adj[0].date == date(2026, 1, 10)
    assert adj[0].merchant == "Apple"
    assert adj[1].date == date(2026, 1, 10)
    assert adj[1].merchant == "Apple"
    assert adj[1].category == "Groceries"
    assert adj[2].date == date(2026, 1, 20)


def test_mixed_expenses_and_refunds() -> None:
    alice, _bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            amount=Decimal("20.00"),  # refund
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]

    adj = compute_adjustments(txs, alice)
    assert len(adj) == 2
    credits = sum(a.amount for a in adj if a.amount > 0)
    debits = sum(a.amount for a in adj if a.amount < 0)
    assert credits == Decimal("50.00")
    assert debits == Decimal("-10.00")


def test_non_shared_transactions_skipped() -> None:
    alice, _bob = _alice_bob()
    txs = [
        make_transaction(
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=None,  # not shared
        )
    ]

    assert compute_adjustments(txs, alice) == []


def test_account_comes_from_target_person() -> None:
    alice, bob = _alice_bob()
    txs = [make_transaction(amount=Decimal("-100.00"), payer_person_id=alice.id)]

    alice_adj = compute_adjustments(txs, alice)
    assert alice_adj[0].account == "Alice Adjustments"

    bob_adj = compute_adjustments(txs, bob)
    assert bob_adj[0].account == "Bob Adjustments"
