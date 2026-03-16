from collections import defaultdict
from uuid import UUID

from attrs import define

from src.domain.entities.settlement import Settlement
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


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

    from_person = await uow.persons.get_by_id(from_person_id)
    if not from_person:
        raise NotFoundError(f"Person {from_person_id} not found")

    to_person = await uow.persons.get_by_id(to_person_id)
    if not to_person:
        raise NotFoundError(f"Person {to_person_id} not found")
