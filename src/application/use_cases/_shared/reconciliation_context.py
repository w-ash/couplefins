from uuid import UUID

from attrs import define

from src.domain.entities.category import Category
from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.person import Person
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ReconciliationContext:
    persons: list[Person]
    categories: list[Category]
    category_groups: list[CategoryGroup]

    @property
    def person_ids(self) -> list[UUID]:
        return [p.id for p in self.persons]


async def load_reconciliation_context(
    uow: UnitOfWorkProtocol,
) -> ReconciliationContext:
    persons = await uow.persons.get_all()
    categories = await uow.categories.get_all()
    category_groups = await uow.category_groups.get_all()
    return ReconciliationContext(
        persons=persons,
        categories=categories,
        category_groups=category_groups,
    )
