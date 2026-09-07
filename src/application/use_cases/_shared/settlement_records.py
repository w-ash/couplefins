from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from attrs import define, field

from src.domain.entities.settlement import Settlement
from src.domain.entities.settlement_portion import SettlementPortion
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.ledger import LedgerMonth, plan_portions
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


def build_settlement(  # noqa: PLR0913
    *,
    from_person_id: UUID,
    to_person_id: UUID,
    amount: Decimal,
    method: str | None,
    is_waived: bool,
    notes: str,
    settled_at: datetime | None = None,
) -> Settlement:
    now = datetime.now(UTC)
    return Settlement(
        id=uuid4(),
        amount=amount,
        from_person_id=from_person_id,
        to_person_id=to_person_id,
        method=method,
        is_waived=is_waived,
        notes=notes,
        settled_at=settled_at or now,
        created_at=now,
    )


def derive_direction_from_legs(
    legs: Iterable[Transaction], person_ids: Iterable[UUID]
) -> tuple[UUID, UUID]:
    """Derive a settlement's (from, to) from its linked transfer legs.

    A negative leg names its payer as the sender; a positive leg names its
    payer as the recipient. A single leg fills the missing side with the
    other member of the couple. Contradictory legs raise ValidationError.
    """
    senders = {tx.payer_person_id for tx in legs if tx.amount < 0}
    recipients = {tx.payer_person_id for tx in legs if tx.amount > 0}
    if len(senders) > 1 or len(recipients) > 1 or (senders and senders == recipients):
        raise ValidationError(
            "Linked transactions imply contradictory settlement directions"
        )
    sender = next(iter(senders), None)
    recipient = next(iter(recipients), None)
    if sender is None and recipient is None:
        raise ValidationError(
            "Cannot derive settlement direction from the linked transactions"
        )
    if sender is None:
        sender = next((pid for pid in person_ids if pid != recipient), None)
    if recipient is None:
        recipient = next((pid for pid in person_ids if pid != sender), None)
    if sender is None or recipient is None:
        raise ValidationError(
            "Cannot derive settlement direction from the linked transactions"
        )
    return sender, recipient


def assert_legs_match_direction(
    legs: Iterable[Transaction], from_person_id: UUID, to_person_id: UUID
) -> None:
    """Reject legs whose sign and payer contradict a settlement's direction.

    A negative leg's payer must be the settlement's sender; a positive
    leg's payer must be its recipient. Zero-amount legs carry no signal.
    """
    for tx in legs:
        if (tx.amount < 0 and tx.payer_person_id != from_person_id) or (
            tx.amount > 0 and tx.payer_person_id != to_person_id
        ):
            raise ValidationError(
                f"Transaction {tx.id} contradicts the settlement's direction"
            )


@define(frozen=True, slots=True)
class SettlementRecord:
    settlement: Settlement
    linked_transaction_ids: list[UUID]
    linked_transactions: list[Transaction] = field(factory=list)


async def enrich_with_links(
    settlements: list[Settlement], uow: UnitOfWorkProtocol
) -> list[SettlementRecord]:
    if not settlements:
        return []

    settlement_ids = [s.id for s in settlements]
    all_links = await uow.settlement_transaction_links.get_by_settlement_ids(
        settlement_ids
    )
    links_by_settlement: dict[UUID, list[UUID]] = defaultdict(list)
    all_tx_ids: list[UUID] = []
    for link in all_links:
        links_by_settlement[link.settlement_id].append(link.transaction_id)
        all_tx_ids.append(link.transaction_id)
    tx_by_id: dict[UUID, Transaction] = {}
    if all_tx_ids:
        txs = await uow.transactions.get_by_ids(all_tx_ids)
        tx_by_id = {tx.id: tx for tx in txs}

    return [
        SettlementRecord(
            settlement=s,
            linked_transaction_ids=links_by_settlement.get(s.id, []),
            linked_transactions=[
                tx_by_id[tid]
                for tid in links_by_settlement.get(s.id, [])
                if tid in tx_by_id
            ],
        )
        for s in settlements
    ]


async def assert_transactions_not_linked(
    uow: UnitOfWorkProtocol, transaction_ids: Iterable[UUID]
) -> None:
    """Reject linking a transaction that already belongs to a settlement.

    A clean 422 instead of the IntegrityError 500 the unique index on
    settlement_transaction_links.transaction_id would raise.
    """
    ids = list(transaction_ids)
    if not ids:
        return
    existing = await uow.settlement_transaction_links.get_by_transaction_ids(ids)
    if existing:
        linked = min((link.transaction_id for link in existing), key=str)
        raise ValidationError(f"Transaction {linked} is already linked to a settlement")


async def allocate_and_save_portions(
    uow: UnitOfWorkProtocol,
    settlement: Settlement,
    ledger_months: Iterable[LedgerMonth],
    covered_months: list[tuple[int, int]],
) -> None:
    """Plan a saved settlement's per-month portions and persist them.

    No covered months recorded defaults to the settled_at month. Pass a
    ledger computed *before* the settlement was saved — the plan zeroes the
    pre-payment balances.
    """
    covered = covered_months or [
        (settlement.settled_at.year, settlement.settled_at.month)
    ]
    plans = plan_portions(
        ledger_months, settlement.amount, settlement.from_person_id, covered
    )
    await uow.settlement_portions.save_batch([
        SettlementPortion(
            id=uuid4(),
            settlement_id=settlement.id,
            year=plan.year,
            month=plan.month,
            amount=plan.amount,
        )
        for plan in plans
    ])


async def validate_settlement_persons(
    from_person_id: UUID, to_person_id: UUID, uow: UnitOfWorkProtocol
) -> None:
    if from_person_id == to_person_id:
        raise ValidationError("from_person_id and to_person_id must differ")

    persons = await uow.persons.get_by_ids([from_person_id, to_person_id])
    found_ids = {p.id for p in persons}
    if from_person_id not in found_ids:
        raise NotFoundError(f"Person {from_person_id} not found")
    if to_person_id not in found_ids:
        raise NotFoundError(f"Person {to_person_id} not found")
