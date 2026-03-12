import pytest

from src.application.use_cases.finalize_period import (
    FinalizePeriodCommand,
    FinalizePeriodUseCase,
)
from src.domain.exceptions import ValidationError
from tests.fixtures.factories import make_reconciliation_period
from tests.fixtures.mocks import make_mock_uow


async def test_creates_period_when_none_exists() -> None:
    uow = make_mock_uow()
    uow.reconciliation_periods.save.side_effect = lambda p: p

    command = FinalizePeriodCommand(year=2026, month=1, notes="Reviewed")
    result = await FinalizePeriodUseCase().execute(command, uow)

    assert result.period.is_finalized is True
    assert result.period.finalized_at is not None
    assert result.period.notes == "Reviewed"
    uow.reconciliation_periods.save.assert_called_once()
    uow.commit.assert_called_once()


async def test_evolves_existing_unfinalized_period() -> None:
    uow = make_mock_uow()
    existing = make_reconciliation_period(year=2026, month=1, is_finalized=False)
    uow.reconciliation_periods.get_by_period.return_value = existing
    uow.reconciliation_periods.save.side_effect = lambda p: p

    command = FinalizePeriodCommand(year=2026, month=1)
    result = await FinalizePeriodUseCase().execute(command, uow)

    assert result.period.id == existing.id
    assert result.period.is_finalized is True
    assert result.period.finalized_at is not None
    uow.commit.assert_called_once()


async def test_rejects_already_finalized() -> None:
    uow = make_mock_uow()
    existing = make_reconciliation_period(year=2026, month=1, is_finalized=True)
    uow.reconciliation_periods.get_by_period.return_value = existing

    command = FinalizePeriodCommand(year=2026, month=1)
    with pytest.raises(ValidationError, match="already finalized"):
        await FinalizePeriodUseCase().execute(command, uow)

    uow.commit.assert_not_called()


def test_validates_month_range() -> None:
    with pytest.raises(ValueError, match="must be 1-12"):
        FinalizePeriodCommand(year=2026, month=13)


def test_validates_positive_year() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        FinalizePeriodCommand(year=0, month=1)
