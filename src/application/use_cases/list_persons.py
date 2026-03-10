from src.domain.entities.person import Person
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


class ListPersonsUseCase:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    async def execute(self) -> list[Person]:
        return await self._uow.persons.get_all()


async def list_persons(uow: UnitOfWorkProtocol) -> list[Person]:
    return await ListPersonsUseCase(uow).execute()
