import pytest

from src.application.use_cases.setup_couple import (
    SetupCoupleCommand,
    SetupCoupleUseCase,
)
from src.domain.exceptions import DuplicateError, ValidationError
from tests.fixtures.factories import make_person
from tests.fixtures.mocks import make_mock_uow

_PW1 = "password123"
_PW2 = "password456"


def _make_command(
    name1: str = "Alice",
    name2: str = "Bob",
    password1: str = _PW1,
    password2: str = _PW2,
) -> SetupCoupleCommand:
    return SetupCoupleCommand(
        name1=name1, name2=name2, password1=password1, password2=password2
    )


def _make_use_case() -> SetupCoupleUseCase:
    return SetupCoupleUseCase(hash_password=lambda p: f"hashed:{p}")


async def test_creates_both_persons_and_commits() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    uow.persons.count.return_value = 0
    uow.persons.save_batch.return_value = [alice, bob]

    result = await _make_use_case().execute(_make_command(), uow)

    assert len(result.persons) == 2
    assert result.persons[0].name == "Alice"
    assert result.persons[1].name == "Bob"
    uow.persons.save_batch.assert_called_once()
    saved = uow.persons.save_batch.call_args[0][0]
    assert saved[0].name == "Alice"
    assert saved[1].name == "Bob"
    uow.commit.assert_called_once()


async def test_hashes_passwords() -> None:
    uow = make_mock_uow()
    uow.persons.count.return_value = 0
    uow.persons.save_batch.return_value = [
        make_person(name="Alice"),
        make_person(name="Bob"),
    ]

    await _make_use_case().execute(_make_command(), uow)

    saved = uow.persons.save_batch.call_args[0][0]
    assert saved[0].password_hash == f"hashed:{_PW1}"
    assert saved[1].password_hash == f"hashed:{_PW2}"


async def test_strips_whitespace_from_names() -> None:
    uow = make_mock_uow()
    uow.persons.count.return_value = 0
    uow.persons.save_batch.return_value = [
        make_person(name="Alice"),
        make_person(name="Bob"),
    ]

    await _make_use_case().execute(
        _make_command(name1="  Alice  ", name2="  Bob  "), uow
    )

    saved = uow.persons.save_batch.call_args[0][0]
    assert saved[0].name == "Alice"
    assert saved[1].name == "Bob"


async def test_rejects_when_persons_already_exist() -> None:
    uow = make_mock_uow()
    uow.persons.count.return_value = 2

    with pytest.raises(DuplicateError, match="already set up"):
        await _make_use_case().execute(_make_command(), uow)

    uow.persons.save_batch.assert_not_called()
    uow.commit.assert_not_called()


async def test_rejects_identical_names_case_insensitive() -> None:
    uow = make_mock_uow()
    uow.persons.count.return_value = 0

    with pytest.raises(ValidationError, match="different"):
        await _make_use_case().execute(_make_command(name1="Alice", name2="alice"), uow)

    uow.persons.save_batch.assert_not_called()
    uow.commit.assert_not_called()


async def test_rejects_identical_names_after_stripping() -> None:
    uow = make_mock_uow()
    uow.persons.count.return_value = 0

    with pytest.raises(ValidationError, match="different"):
        await _make_use_case().execute(_make_command(name1="  Bob  ", name2="bob"), uow)

    uow.persons.save_batch.assert_not_called()


async def test_generates_unique_ids_for_each_person() -> None:
    uow = make_mock_uow()
    uow.persons.count.return_value = 0
    uow.persons.save_batch.return_value = [
        make_person(name="Alice"),
        make_person(name="Bob"),
    ]

    await _make_use_case().execute(_make_command(), uow)

    saved = uow.persons.save_batch.call_args[0][0]
    assert saved[0].id != saved[1].id


async def test_rejects_weak_password1() -> None:
    uow = make_mock_uow()
    uow.persons.count.return_value = 0

    with pytest.raises(ValidationError, match="at least 8"):
        await _make_use_case().execute(_make_command(password1="short"), uow)

    uow.persons.save_batch.assert_not_called()


async def test_rejects_weak_password2() -> None:
    uow = make_mock_uow()
    uow.persons.count.return_value = 0

    with pytest.raises(ValidationError, match="at least 8"):
        await _make_use_case().execute(_make_command(password2="short"), uow)

    uow.persons.save_batch.assert_not_called()
