from datetime import UTC, datetime

import pytest

from src.application.use_cases._shared.finalization import (
    assert_period_not_finalized,
    assert_periods_not_finalized,
)
from src.domain.exceptions import PeriodFinalizedError
from tests.fixtures.factories import make_reconciliation_period
from tests.fixtures.mocks import make_mock_uow


async def test_passes_when_period_is_open() -> None:
    uow = make_mock_uow()
    uow.reconciliation_periods.get_by_period.return_value = make_reconciliation_period(
        is_finalized=False
    )
    await assert_period_not_finalized(uow, 2026, 1)


async def test_passes_when_no_period_exists() -> None:
    uow = make_mock_uow()
    # get_by_period already returns None from make_mock_uow
    await assert_period_not_finalized(uow, 2026, 1)


async def test_raises_when_finalized() -> None:
    uow = make_mock_uow()
    uow.reconciliation_periods.get_by_period.return_value = make_reconciliation_period(
        is_finalized=True, finalized_at=datetime.now(UTC)
    )
    with pytest.raises(PeriodFinalizedError, match="2026-01"):
        await assert_period_not_finalized(uow, 2026, 1)


async def test_batch_passes_when_all_open() -> None:
    uow = make_mock_uow()
    await assert_periods_not_finalized(uow, {(2026, 1), (2026, 2)})


async def test_batch_raises_on_first_finalized() -> None:
    uow = make_mock_uow()

    def _get_by_period(_year: int, month: int):
        if month == 2:
            return make_reconciliation_period(
                month=2, is_finalized=True, finalized_at=datetime.now(UTC)
            )
        return None

    uow.reconciliation_periods.get_by_period.side_effect = _get_by_period
    with pytest.raises(PeriodFinalizedError, match="2026-02"):
        await assert_periods_not_finalized(uow, {(2026, 1), (2026, 2)})
