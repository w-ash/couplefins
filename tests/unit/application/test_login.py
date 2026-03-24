import pytest

from src.application.use_cases.auth.login import LoginCommand, LoginResult, LoginUseCase
from src.domain.exceptions import AuthenticationError
from tests.fixtures.factories import make_person
from tests.fixtures.mocks import make_mock_uow

_HASHED = "$argon2id$fake-hash"


def _make_use_case(
    verify_result: bool = True,
    token: str = "test-token",
) -> LoginUseCase:
    return LoginUseCase(
        verify_password=lambda _plain, _hashed: verify_result,
        create_token=lambda _pid: token,
    )


async def test_login_success() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice", password_hash=_HASHED)
    uow.persons.get_by_name.return_value = alice

    result = await _make_use_case().execute(
        LoginCommand(name="Alice", password="secret123"), uow
    )

    assert isinstance(result, LoginResult)
    assert result.person.name == "Alice"
    assert result.token == "test-token"


async def test_login_wrong_name() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_name.return_value = None

    with pytest.raises(AuthenticationError, match="Invalid name or password"):
        await _make_use_case().execute(
            LoginCommand(name="Nobody", password="secret123"), uow
        )


async def test_login_wrong_password() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice", password_hash=_HASHED)
    uow.persons.get_by_name.return_value = alice

    with pytest.raises(AuthenticationError, match="Invalid name or password"):
        await _make_use_case(verify_result=False).execute(
            LoginCommand(name="Alice", password="wrongpass"), uow
        )


async def test_login_no_password_set() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice", password_hash="")
    uow.persons.get_by_name.return_value = alice

    with pytest.raises(AuthenticationError, match="Invalid name or password"):
        await _make_use_case().execute(
            LoginCommand(name="Alice", password="secret123"), uow
        )
