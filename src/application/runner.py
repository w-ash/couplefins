from collections.abc import Awaitable, Callable

from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.infrastructure.persistence.database.db_connection import get_session
from src.infrastructure.persistence.repositories.factories import get_unit_of_work


async def execute_use_case[TResult](
    use_case_factory: Callable[[UnitOfWorkProtocol], Awaitable[TResult]],
) -> TResult:
    async with get_session() as session:
        uow = get_unit_of_work(session)
        return await use_case_factory(uow)
