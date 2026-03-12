from datetime import date
from decimal import Decimal
from uuid import UUID, uuid5

from attrs import define

from src.domain.entities.person import Person
from src.domain.entities.transaction import Transaction
from src.domain.splits import compute_shares

_DEDUP_HEX_LENGTH = 12

# Fixed namespace for deterministic UUID5 derivation of dedup IDs.
COUPLEFINS_NAMESPACE = UUID("7a3f8e2b-1c4d-5a6b-9e0f-d2c3b4a5e6f7")


@define(frozen=True, slots=True)
class Adjustment:
    dedup_id: str
    source_transaction_id: UUID
    date: date
    merchant: str
    category: str
    amount: Decimal
    account: str


def compute_adjustments(
    transactions: list[Transaction],
    target_person: Person,
) -> list[Adjustment]:
    adjustments: list[Adjustment] = []

    for tx in transactions:
        if not tx.is_shared:
            continue
        _, other_share = compute_shares(tx.amount, tx.payer_percentage)
        if other_share == 0:
            continue

        is_payer = tx.payer_person_id == target_person.id
        is_expense = tx.amount < 0

        # Payer gets credit (positive) for expenses, debit (negative) for refunds.
        # Non-payer gets debit (negative) for expenses, credit (positive) for refunds.
        signed_amount = other_share if is_payer == is_expense else -other_share

        dedup_id = uuid5(COUPLEFINS_NAMESPACE, f"{tx.id}:{target_person.id}").hex[
            :_DEDUP_HEX_LENGTH
        ]

        adjustments.append(
            Adjustment(
                dedup_id=dedup_id,
                source_transaction_id=tx.id,
                date=tx.date,
                merchant=tx.merchant,
                category=tx.category,
                amount=signed_amount,
                account=target_person.adjustment_account,
            )
        )

    adjustments.sort(
        key=lambda a: (a.date, a.merchant, a.category, a.source_transaction_id)
    )
    return adjustments
