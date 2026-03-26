import pytest

from src.application.use_cases.auth.set_initial_password import (
    SetInitialPasswordCommand,
    SetInitialPasswordResult,
    SetInitialPasswordUseCase,
)
from src.domain.exceptions import AuthenticationError, ValidationError
from tests.fixtures.factories import make_person
from tests.fixtures.mocks import make_mock_uow

_TOKEN = "test-token"
_HASHED = "$argon2id$fake-hash"


def _make_use_case() -> SetInitialPasswordUseCase:
    return SetInitialPasswordUseCase(
        hash_password=lambda _plain: _HASHED,
        create_token=lambda _pid: _TOKEN,
    )


async def test_set_initial_password_success() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice", password_hash="")
    uow.persons.get_by_name.return_value = alice

    result = await _make_use_case().execute(
        SetInitialPasswordCommand(name="Alice", new_password="longpassword"), uow
    )

    assert isinstance(result, SetInitialPasswordResult)
    assert result.person.name == "Alice"
    assert result.person.password_hash == _HASHED
    assert result.token == _TOKEN
    uow.persons.save.assert_awaited_once()
    uow.commit.assert_awaited_once()


async def test_set_initial_password_person_not_found() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_name.return_value = None

    with pytest.raises(AuthenticationError, match="Person not found"):
        await _make_use_case().execute(
            SetInitialPasswordCommand(name="Nobody", new_password="longpassword"), uow
        )


async def test_set_initial_password_already_set() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice", password_hash=_HASHED)
    uow.persons.get_by_name.return_value = alice

    with pytest.raises(ValidationError, match="Password is already set"):
        await _make_use_case().execute(
            SetInitialPasswordCommand(name="Alice", new_password="longpassword"), uow
        )


async def test_set_initial_password_too_short() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice", password_hash="")
    uow.persons.get_by_name.return_value = alice

    with pytest.raises(ValidationError, match="at least 8 characters"):
        await _make_use_case().execute(
            SetInitialPasswordCommand(name="Alice", new_password="short"), uow
        )
