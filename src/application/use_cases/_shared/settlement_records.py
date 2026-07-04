from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from attrs import define, field

from src.domain.entities.settlement import Settlement
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


def build_settlement(  # noqa: PLR0913
    *,
    year: int | None,
    month: int | None,
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
        year=year,
        month=month,
        amount=amount,
        from_person_id=from_person_id,
        to_person_id=to_person_id,
        method=method,
        is_waived=is_waived,
        notes=notes,
        settled_at=settled_at or now,
        created_at=now,
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
    for tx_id in transaction_ids:
        existing = await uow.settlement_transaction_links.get_by_transaction_id(tx_id)
        if existing:
            raise ValidationError(
                f"Transaction {tx_id} is already linked to a settlement"
            )


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
