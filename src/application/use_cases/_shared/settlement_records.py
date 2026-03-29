from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from attrs import define

from src.domain.entities.settlement import Settlement, SettlementMethod
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


def build_settlement(  # noqa: PLR0913
    *,
    year: int,
    month: int,
    from_person_id: UUID,
    to_person_id: UUID,
    amount: Decimal,
    method: SettlementMethod | None,
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
    for link in all_links:
        links_by_settlement[link.settlement_id].append(link.transaction_id)

    return [
        SettlementRecord(
            settlement=s,
            linked_transaction_ids=links_by_settlement.get(s.id, []),
        )
        for s in settlements
    ]


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
