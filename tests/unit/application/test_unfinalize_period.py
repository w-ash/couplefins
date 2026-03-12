from datetime import UTC, datetime

import pytest

from src.application.use_cases.unfinalize_period import (
    UnfinalizePeriodCommand,
    UnfinalizePeriodUseCase,
)
from src.domain.exceptions import ValidationError
from tests.fixtures.factories import make_reconciliation_period
from tests.fixtures.mocks import make_mock_uow


async def test_unfinalizes_finalized_period() -> None:
    uow = make_mock_uow()
    existing = make_reconciliation_period(
        year=2026,
        month=1,
        is_finalized=True,
        finalized_at=datetime.now(UTC),
        notes="Reviewed",
    )
    uow.reconciliation_periods.get_by_period.return_value = existing
    uow.reconciliation_periods.save.side_effect = lambda p: p

    command = UnfinalizePeriodCommand(year=2026, month=1)
    result = await UnfinalizePeriodUseCase().execute(command, uow)

    assert result.period.is_finalized is False
    assert result.period.finalized_at is None
    assert not result.period.notes
    uow.commit.assert_called_once()


async def test_rejects_when_not_finalized() -> None:
    uow = make_mock_uow()
    existing = make_reconciliation_period(year=2026, month=1, is_finalized=False)
    uow.reconciliation_periods.get_by_period.return_value = existing

    command = UnfinalizePeriodCommand(year=2026, month=1)
    with pytest.raises(ValidationError, match="not finalized"):
        await UnfinalizePeriodUseCase().execute(command, uow)

    uow.commit.assert_not_called()


async def test_rejects_when_no_period_exists() -> None:
    uow = make_mock_uow()
    # get_by_period already returns None from make_mock_uow

    command = UnfinalizePeriodCommand(year=2026, month=1)
    with pytest.raises(ValidationError, match="not finalized"):
        await UnfinalizePeriodUseCase().execute(command, uow)
