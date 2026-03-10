from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.repositories.unit_of_work import UnitOfWork


def get_unit_of_work(session: AsyncSession) -> UnitOfWork:
    return UnitOfWork(session)
