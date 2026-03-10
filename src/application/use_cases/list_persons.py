from attrs import define

from src.domain.entities.person import Person
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class ListPersonsCommand:
    """Parameterless — exists for API uniformity."""


@define(frozen=True, slots=True)
class ListPersonsResult:
    persons: list[Person]


@define(slots=True)
class ListPersonsUseCase:
    async def execute(
        self, _command: ListPersonsCommand, uow: UnitOfWorkProtocol
    ) -> ListPersonsResult:
        async with uow:
            persons = await uow.persons.get_all()
            return ListPersonsResult(persons=persons)


async def list_persons(uow: UnitOfWorkProtocol) -> ListPersonsResult:
    return await ListPersonsUseCase().execute(ListPersonsCommand(), uow)
