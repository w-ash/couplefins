from decimal import Decimal

import pytest

from src.application.use_cases.copy_budgets import (
    CopyBudgetsCommand,
    CopyBudgetsUseCase,
)
from src.domain.exceptions import PeriodFinalizedError, ValidationError
from tests.fixtures.factories import (
    make_category_group,
    make_category_group_budget,
    make_person,
    make_reconciliation_period,
)
from tests.fixtures.mocks import make_mock_uow


def _base_command(person_id: ...) -> CopyBudgetsCommand:
    return CopyBudgetsCommand(
        source_year=2026,
        source_month=1,
        target_year=2026,
        target_month=2,
        person_id=person_id,
    )


async def test_copies_household_and_personal_budgets() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    food = make_category_group(name="Food")
    travel = make_category_group(name="Travel")
    personal_grp = make_category_group(name="Personal")

    household_b1 = make_category_group_budget(group_id=food.id, year=2026, month=1)
    household_b2 = make_category_group_budget(group_id=travel.id, year=2026, month=1)
    personal_b = make_category_group_budget(
        group_id=personal_grp.id, year=2026, month=1, person_id=alice.id
    )

    uow.category_group_budgets.get_by_month.side_effect = [
        [household_b1, household_b2],  # source household
        [personal_b],  # source personal
        [],  # target household
        [],  # target personal
    ]
    uow.category_group_budgets.save_batch.return_value = []

    command = _base_command(person_id=alice.id)
    result = await CopyBudgetsUseCase().execute(command, uow)

    assert result.copied_count == 3
    assert result.skipped_count == 0
    uow.category_group_budgets.save_batch.assert_called_once()
    saved = uow.category_group_budgets.save_batch.call_args[0][0]
    assert len(saved) == 3
    assert all(b.year == 2026 and b.month == 2 for b in saved)
    uow.commit.assert_called_once()


async def test_skips_already_budgeted_groups() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    food = make_category_group(name="Food")
    travel = make_category_group(name="Travel")

    source_food = make_category_group_budget(group_id=food.id, year=2026, month=1)
    source_travel = make_category_group_budget(group_id=travel.id, year=2026, month=1)
    target_food = make_category_group_budget(group_id=food.id, year=2026, month=2)

    uow.category_group_budgets.get_by_month.side_effect = [
        [source_food, source_travel],  # source household
        [],  # source personal
        [target_food],  # target household (food already exists)
        [],  # target personal
    ]
    uow.category_group_budgets.save_batch.return_value = []

    command = _base_command(person_id=alice.id)
    result = await CopyBudgetsUseCase().execute(command, uow)

    assert result.copied_count == 1
    assert result.skipped_count == 1
    saved = uow.category_group_budgets.save_batch.call_args[0][0]
    assert saved[0].group_id == travel.id


async def test_does_not_copy_partner_personal_budgets() -> None:
    """Only household + caller's personal are copied, not partner's."""
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    food = make_category_group(name="Food")

    household_b = make_category_group_budget(group_id=food.id, year=2026, month=1)

    # get_by_month calls: source_household, source_personal (alice only), target_household, target_personal
    uow.category_group_budgets.get_by_month.side_effect = [
        [household_b],  # source household
        [],  # source personal (Alice has none — Bob's are excluded by design)
        [],  # target household
        [],  # target personal
    ]
    uow.category_group_budgets.save_batch.return_value = []

    command = _base_command(person_id=alice.id)
    result = await CopyBudgetsUseCase().execute(command, uow)

    assert result.copied_count == 1
    # Verify get_by_month was called with alice.id for personal scope
    calls = uow.category_group_budgets.get_by_month.call_args_list
    assert calls[1].args == (2026, 1, alice.id)  # source personal = alice only


async def test_rejects_finalized_target_month() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")

    uow.reconciliation_periods.get_by_period.return_value = make_reconciliation_period(
        year=2026, month=2, is_finalized=True
    )

    command = _base_command(person_id=alice.id)
    with pytest.raises(PeriodFinalizedError):
        await CopyBudgetsUseCase().execute(command, uow)


async def test_empty_source_copies_nothing() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")

    uow.category_group_budgets.get_by_month.return_value = []

    command = _base_command(person_id=alice.id)
    result = await CopyBudgetsUseCase().execute(command, uow)

    assert result.copied_count == 0
    assert result.skipped_count == 0
    uow.category_group_budgets.save_batch.assert_not_called()
    uow.commit.assert_called_once()


async def test_preserves_exact_decimal_amounts() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    food = make_category_group(name="Food")

    source = make_category_group_budget(
        group_id=food.id, year=2026, month=1, monthly_amount=Decimal("123.45")
    )

    uow.category_group_budgets.get_by_month.side_effect = [
        [source],  # source household
        [],  # source personal
        [],  # target household
        [],  # target personal
    ]
    uow.category_group_budgets.save_batch.return_value = []

    command = _base_command(person_id=alice.id)
    await CopyBudgetsUseCase().execute(command, uow)

    saved = uow.category_group_budgets.save_batch.call_args[0][0]
    assert saved[0].monthly_amount == Decimal("123.45")
    assert saved[0].id != source.id  # new UUID


def test_rejects_same_source_and_target_month() -> None:
    alice = make_person(name="Alice")
    with pytest.raises(ValidationError, match="must differ"):
        CopyBudgetsCommand(
            source_year=2026,
            source_month=1,
            target_year=2026,
            target_month=1,
            person_id=alice.id,
        )
