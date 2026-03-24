import uuid

import pytest

from src.application.use_cases.auth.change_password import (
    ChangePasswordCommand,
    ChangePasswordUseCase,
)
from src.domain.exceptions import AuthenticationError, ValidationError
from tests.fixtures.factories import make_person
from tests.fixtures.mocks import make_mock_uow

_PERSON_ID = uuid.uuid4()
_HASHED = "$argon2id$fake-hash"


def _make_use_case(verify_result: bool = True) -> ChangePasswordUseCase:
    return ChangePasswordUseCase(
        verify_password=lambda _plain, _hashed: verify_result,
        hash_password=lambda p: f"hashed:{p}",
    )


async def test_change_password_success() -> None:
    uow = make_mock_uow()
    alice = make_person(id=_PERSON_ID, name="Alice", password_hash=_HASHED)
    uow.persons.get_by_id.return_value = alice
    uow.persons.save.return_value = alice

    result = await _make_use_case().execute(
        ChangePasswordCommand(
            person_id=_PERSON_ID,
            current_password="oldpass123",
            new_password="newpass123",
        ),
        uow,
    )

    assert result.success is True
    uow.persons.save.assert_called_once()
    saved = uow.persons.save.call_args[0][0]
    assert saved.password_hash == "hashed:newpass123"
    uow.commit.assert_called_once()


async def test_change_password_wrong_current() -> None:
    uow = make_mock_uow()
    alice = make_person(id=_PERSON_ID, name="Alice", password_hash=_HASHED)
    uow.persons.get_by_id.return_value = alice

    with pytest.raises(AuthenticationError, match="Current password is incorrect"):
        await _make_use_case(verify_result=False).execute(
            ChangePasswordCommand(
                person_id=_PERSON_ID,
                current_password="wrongpass",
                new_password="newpass123",
            ),
            uow,
        )

    uow.persons.save.assert_not_called()


async def test_change_password_weak_new_password() -> None:
    uow = make_mock_uow()
    alice = make_person(id=_PERSON_ID, name="Alice", password_hash=_HASHED)
    uow.persons.get_by_id.return_value = alice

    with pytest.raises(ValidationError, match="at least 8"):
        await _make_use_case().execute(
            ChangePasswordCommand(
                person_id=_PERSON_ID,
                current_password="oldpass123",
                new_password="short",
            ),
            uow,
        )

    uow.persons.save.assert_not_called()
