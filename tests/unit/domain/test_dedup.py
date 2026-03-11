from decimal import Decimal

from src.domain.dedup import classify_transactions, natural_key
from tests.fixtures.factories import make_transaction


def test_natural_key_extracts_correct_fields() -> None:
    tx = make_transaction(amount=Decimal("-42.00"), account="Amex", occurrence=1)
    key = natural_key(tx)

    assert key.date == tx.date
    assert key.amount == tx.amount
    assert key.account == "Amex"
    assert key.original_statement == tx.original_statement
    assert key.occurrence == 1
    assert key.payer_person_id == tx.payer_person_id


def test_classify_all_new() -> None:
    incoming = [make_transaction(), make_transaction(merchant="Coffee")]
    result = classify_transactions(incoming, existing=[])

    assert len(result) == 2
    assert all(c.status == "new" for c in result)
    assert all(c.existing_id is None for c in result)
    assert all(c.diffs == () for c in result)


def test_classify_all_unchanged() -> None:
    person_id = make_transaction().payer_person_id
    tx = make_transaction(payer_person_id=person_id)
    # Existing has same natural key and same mutable fields
    existing = make_transaction(
        date=tx.date,
        amount=tx.amount,
        account=tx.account,
        original_statement=tx.original_statement,
        payer_person_id=tx.payer_person_id,
        merchant=tx.merchant,
        category=tx.category,
        notes=tx.notes,
        tags=tx.tags,
        payer_percentage=tx.payer_percentage,
    )
    result = classify_transactions([tx], [existing])

    assert len(result) == 1
    assert result[0].status == "unchanged"
    assert result[0].existing_id == existing.id
    assert result[0].diffs == ()


def test_classify_changed_merchant() -> None:
    person_id = make_transaction().payer_person_id
    existing = make_transaction(
        merchant="Old Name",
        payer_person_id=person_id,
    )
    incoming = make_transaction(
        date=existing.date,
        amount=existing.amount,
        account=existing.account,
        original_statement=existing.original_statement,
        payer_person_id=existing.payer_person_id,
        merchant="New Name",
        category=existing.category,
        notes=existing.notes,
        tags=existing.tags,
        payer_percentage=existing.payer_percentage,
    )

    result = classify_transactions([incoming], [existing])

    assert len(result) == 1
    assert result[0].status == "changed"
    assert result[0].existing_id == existing.id
    assert len(result[0].diffs) == 1
    assert result[0].diffs[0].field_name == "merchant"
    assert result[0].diffs[0].old_value == "Old Name"
    assert result[0].diffs[0].new_value == "New Name"


def test_classify_changed_tags_and_payer_percentage() -> None:
    person_id = make_transaction().payer_person_id
    existing = make_transaction(
        payer_person_id=person_id,
        tags=("shared",),
        payer_percentage=50,
    )
    incoming = make_transaction(
        date=existing.date,
        amount=existing.amount,
        account=existing.account,
        original_statement=existing.original_statement,
        payer_person_id=existing.payer_person_id,
        merchant=existing.merchant,
        category=existing.category,
        notes=existing.notes,
        tags=("shared", "s70"),
        payer_percentage=70,
    )

    result = classify_transactions([incoming], [existing])

    assert result[0].status == "changed"
    field_names = {d.field_name for d in result[0].diffs}
    assert "tags" in field_names
    assert "payer_percentage" in field_names


def test_different_occurrence_classified_as_separate() -> None:
    person_id = make_transaction().payer_person_id
    tx_a = make_transaction(
        original_statement="CLIPPER TRANSIT FARE",
        payer_person_id=person_id,
        occurrence=0,
    )
    tx_b = make_transaction(
        date=tx_a.date,
        amount=tx_a.amount,
        account=tx_a.account,
        original_statement=tx_a.original_statement,
        payer_person_id=person_id,
        occurrence=1,
    )

    result = classify_transactions([tx_a, tx_b], existing=[])

    assert len(result) == 2
    assert all(c.status == "new" for c in result)


def test_classify_mixed_batch() -> None:
    person_id = make_transaction().payer_person_id
    # Existing transaction
    existing = make_transaction(
        original_statement="GROCERY STORE #123",
        payer_person_id=person_id,
        merchant="Grocery",
    )

    # Incoming: one matches (unchanged), one matches with change, one is new
    unchanged = make_transaction(
        date=existing.date,
        amount=existing.amount,
        account=existing.account,
        original_statement=existing.original_statement,
        payer_person_id=existing.payer_person_id,
        merchant=existing.merchant,
        category=existing.category,
        notes=existing.notes,
        tags=existing.tags,
        payer_percentage=existing.payer_percentage,
    )
    new_tx = make_transaction(
        original_statement="COFFEE SHOP #456",
        payer_person_id=person_id,
    )

    result = classify_transactions([unchanged, new_tx], [existing])

    statuses = {c.status for c in result}
    assert statuses == {"unchanged", "new"}
