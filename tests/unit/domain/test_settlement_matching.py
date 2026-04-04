from decimal import Decimal

from src.domain.settlement_matching import find_settlement_candidates
from tests.fixtures.factories import make_settlement_merchant, make_transaction


def test_merchant_match_scores_high() -> None:
    tx = make_transaction(
        merchant="Venmo Payment",
        amount=Decimal("-200.00"),
        household=False,
    )
    merchants = [make_settlement_merchant(name="Venmo", merchant_pattern="venmo")]
    candidates = find_settlement_candidates([tx], Decimal("200.00"), merchants)

    assert len(candidates) == 1
    assert candidates[0].score >= 3
    assert any("Venmo" in r for r in candidates[0].match_reasons)


def test_amount_match_scores_high() -> None:
    tx = make_transaction(
        merchant="Some Transfer",
        amount=Decimal("-150.25"),
        household=False,
    )
    candidates = find_settlement_candidates([tx], Decimal("150.25"), [])

    assert len(candidates) == 1
    assert any("Amount" in r for r in candidates[0].match_reasons)


def test_amount_within_tolerance() -> None:
    tx = make_transaction(
        merchant="Transfer",
        amount=Decimal("-100.30"),
        household=False,
    )
    candidates = find_settlement_candidates([tx], Decimal("100.00"), [])

    assert len(candidates) == 1
    assert any("Amount" in r for r in candidates[0].match_reasons)


def test_amount_outside_tolerance_no_amount_reason() -> None:
    tx = make_transaction(
        merchant="Transfer",
        amount=Decimal("-101.00"),
        household=False,
    )
    candidates = find_settlement_candidates([tx], Decimal("100.00"), [])

    assert len(candidates) == 1
    assert not any("Amount" in r for r in candidates[0].match_reasons)


def test_settlement_transactions_disqualified() -> None:
    tx = make_transaction(
        merchant="Venmo",
        amount=Decimal("-200.00"),
        is_settlement=True,
    )
    merchants = [make_settlement_merchant()]
    candidates = find_settlement_candidates([tx], Decimal("200.00"), merchants)

    assert len(candidates) == 0


def test_excluded_transactions_disqualified() -> None:
    tx = make_transaction(
        merchant="Venmo",
        amount=Decimal("-200.00"),
        is_excluded=True,
    )
    merchants = [make_settlement_merchant()]
    candidates = find_settlement_candidates([tx], Decimal("200.00"), merchants)

    assert len(candidates) == 0


def test_category_transfer_scores() -> None:
    tx = make_transaction(
        merchant="Bank",
        category="Transfer",
        amount=Decimal("-50.00"),
        household=False,
    )
    candidates = find_settlement_candidates([tx], Decimal("50.00"), [])

    assert len(candidates) == 1
    assert any("Category" in r for r in candidates[0].match_reasons)


def test_personal_transaction_scores() -> None:
    tx = make_transaction(
        merchant="Venmo",
        amount=Decimal("-50.00"),
        household=False,
    )
    merchants = [make_settlement_merchant()]
    candidates = find_settlement_candidates([tx], Decimal("50.00"), merchants)

    assert len(candidates) == 1
    assert any("Personal" in r for r in candidates[0].match_reasons)


def test_sorted_by_score_descending() -> None:
    tx_high = make_transaction(
        merchant="Venmo",
        amount=Decimal("-100.00"),
        household=False,
    )
    tx_low = make_transaction(
        merchant="Random Store",
        amount=Decimal("-100.00"),
        household=False,
    )
    merchants = [make_settlement_merchant()]
    candidates = find_settlement_candidates(
        [tx_low, tx_high], Decimal("100.00"), merchants
    )

    assert len(candidates) == 2
    assert candidates[0].score >= candidates[1].score


def test_capped_at_20() -> None:
    txs = [
        make_transaction(
            merchant="Venmo",
            amount=Decimal(f"-{i}.00"),
            household=False,
        )
        for i in range(1, 30)
    ]
    merchants = [make_settlement_merchant()]
    candidates = find_settlement_candidates(txs, Decimal("15.00"), merchants)

    assert len(candidates) <= 20


def test_empty_transactions_returns_empty() -> None:
    candidates = find_settlement_candidates([], Decimal("100.00"), [])
    assert candidates == []


def test_original_statement_match() -> None:
    tx = make_transaction(
        merchant="BANK TRANSFER",
        original_statement="VENMO PAYMENT 12345",
        amount=Decimal("-200.00"),
        household=False,
    )
    merchants = [make_settlement_merchant(name="Venmo", merchant_pattern="venmo")]
    candidates = find_settlement_candidates([tx], Decimal("200.00"), merchants)

    assert len(candidates) == 1
    assert any("Venmo" in r for r in candidates[0].match_reasons)


def test_zero_score_excluded() -> None:
    tx = make_transaction(
        merchant="Grocery Store",
        category="Groceries",
        amount=Decimal("-999.00"),
        household=True,
    )
    candidates = find_settlement_candidates([tx], Decimal("50.00"), [])
    assert candidates == []


def test_equal_score_sorted_by_date() -> None:
    from datetime import date

    tx_later = make_transaction(
        merchant="Venmo",
        amount=Decimal("-50.00"),
        household=False,
        date=date(2026, 3, 20),
    )
    tx_earlier = make_transaction(
        merchant="Venmo",
        amount=Decimal("-50.00"),
        household=False,
        date=date(2026, 3, 10),
    )
    merchants = [make_settlement_merchant()]
    candidates = find_settlement_candidates(
        [tx_later, tx_earlier], Decimal("50.00"), merchants
    )
    assert len(candidates) == 2
    assert candidates[0].transaction.date < candidates[1].transaction.date


def test_credit_card_payment_category_matches() -> None:
    tx = make_transaction(
        merchant="Bank",
        category="Credit Card Payment",
        amount=Decimal("-50.00"),
        household=False,
    )
    candidates = find_settlement_candidates([tx], Decimal("50.00"), [])
    assert len(candidates) == 1
    assert any("Category" in r for r in candidates[0].match_reasons)
