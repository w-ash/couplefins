from uuid import UUID

from attrs import define

from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.category_mapping import CategoryMapping
from src.domain.entities.person import Person
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ReconciliationContext:
    persons: list[Person]
    category_mappings: list[CategoryMapping]
    category_groups: list[CategoryGroup]

    @property
    def person_ids(self) -> list[UUID]:
        return [p.id for p in self.persons]


async def load_reconciliation_context(
    uow: UnitOfWorkProtocol,
) -> ReconciliationContext:
    persons = await uow.persons.get_all()
    category_mappings = await uow.category_mappings.get_all()
    category_groups = await uow.category_groups.get_all()
    return ReconciliationContext(
        persons=persons,
        category_mappings=category_mappings,
        category_groups=category_groups,
    )
