from src.domain.exceptions import PeriodFinalizedError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


async def assert_period_not_finalized(
    uow: UnitOfWorkProtocol, year: int, month: int
) -> None:
    """Raises PeriodFinalizedError if the period is finalized."""
    period = await uow.reconciliation_periods.get_by_period(year, month)
    if period and period.is_finalized:
        raise PeriodFinalizedError(
            f"Period {year}-{month:02d} is finalized and cannot be modified"
        )


async def assert_periods_not_finalized(
    uow: UnitOfWorkProtocol, periods: set[tuple[int, int]]
) -> None:
    """Batch variant — checks multiple (year, month) pairs."""
    for year, month in periods:
        await assert_period_not_finalized(uow, year, month)
