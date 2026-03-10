import pytest

from src.application.use_cases.setup_couple import (
    SetupCoupleCommand,
    SetupCoupleUseCase,
)
from src.domain.exceptions import DuplicateError, ValidationError
from tests.fixtures.factories import make_person
from tests.fixtures.mocks import make_mock_uow


async def test_creates_both_persons_and_commits() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    uow.persons.count.return_value = 0
    uow.persons.save_batch.return_value = [alice, bob]

    result = await SetupCoupleUseCase().execute(
        SetupCoupleCommand(name1="Alice", name2="Bob"), uow
    )

    assert len(result.persons) == 2
    assert result.persons[0].name == "Alice"
    assert result.persons[1].name == "Bob"
    uow.persons.save_batch.assert_called_once()
    saved = uow.persons.save_batch.call_args[0][0]
    assert saved[0].name == "Alice"
    assert saved[1].name == "Bob"
    uow.commit.assert_called_once()


async def test_strips_whitespace_from_names() -> None:
    uow = make_mock_uow()
    uow.persons.count.return_value = 0
    uow.persons.save_batch.return_value = [
        make_person(name="Alice"),
        make_person(name="Bob"),
    ]

    await SetupCoupleUseCase().execute(
        SetupCoupleCommand(name1="  Alice  ", name2="  Bob  "), uow
    )

    saved = uow.persons.save_batch.call_args[0][0]
    assert saved[0].name == "Alice"
    assert saved[1].name == "Bob"


async def test_rejects_when_persons_already_exist() -> None:
    uow = make_mock_uow()
    uow.persons.count.return_value = 2

    with pytest.raises(DuplicateError, match="already set up"):
        await SetupCoupleUseCase().execute(
            SetupCoupleCommand(name1="Alice", name2="Bob"), uow
        )

    uow.persons.save_batch.assert_not_called()
    uow.commit.assert_not_called()


async def test_rejects_identical_names_case_insensitive() -> None:
    uow = make_mock_uow()
    uow.persons.count.return_value = 0

    with pytest.raises(ValidationError, match="different"):
        await SetupCoupleUseCase().execute(
            SetupCoupleCommand(name1="Alice", name2="alice"), uow
        )

    uow.persons.save_batch.assert_not_called()
    uow.commit.assert_not_called()


async def test_rejects_identical_names_after_stripping() -> None:
    uow = make_mock_uow()
    uow.persons.count.return_value = 0

    with pytest.raises(ValidationError, match="different"):
        await SetupCoupleUseCase().execute(
            SetupCoupleCommand(name1="  Bob  ", name2="bob"), uow
        )

    uow.persons.save_batch.assert_not_called()


async def test_generates_unique_ids_for_each_person() -> None:
    uow = make_mock_uow()
    uow.persons.count.return_value = 0
    uow.persons.save_batch.return_value = [
        make_person(name="Alice"),
        make_person(name="Bob"),
    ]

    await SetupCoupleUseCase().execute(
        SetupCoupleCommand(name1="Alice", name2="Bob"), uow
    )

    saved = uow.persons.save_batch.call_args[0][0]
    assert saved[0].id != saved[1].id
