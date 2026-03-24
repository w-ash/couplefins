import uuid

import pytest

from src.application.use_cases.auth.reset_partner_password import (
    ResetPartnerPasswordCommand,
    ResetPartnerPasswordUseCase,
)
from src.domain.exceptions import NotFoundError, ValidationError
from tests.fixtures.factories import make_person
from tests.fixtures.mocks import make_mock_uow

_ALICE_ID = uuid.uuid4()
_BOB_ID = uuid.uuid4()


def _make_use_case() -> ResetPartnerPasswordUseCase:
    return ResetPartnerPasswordUseCase(hash_password=lambda p: f"hashed:{p}")


async def test_reset_partner_password_success() -> None:
    uow = make_mock_uow()
    alice = make_person(id=_ALICE_ID, name="Alice", password_hash="old-hash")
    bob = make_person(id=_BOB_ID, name="Bob", password_hash="bob-hash")
    uow.persons.get_all.return_value = [alice, bob]
    uow.persons.save.return_value = bob

    result = await _make_use_case().execute(
        ResetPartnerPasswordCommand(
            requester_person_id=_ALICE_ID,
            new_password="newpass123",
        ),
        uow,
    )

    assert result.success is True
    uow.persons.save.assert_called_once()
    saved = uow.persons.save.call_args[0][0]
    assert saved.id == _BOB_ID
    assert saved.password_hash == "hashed:newpass123"
    uow.commit.assert_called_once()


async def test_reset_partner_weak_password() -> None:
    uow = make_mock_uow()
    alice = make_person(id=_ALICE_ID, name="Alice")
    bob = make_person(id=_BOB_ID, name="Bob")
    uow.persons.get_all.return_value = [alice, bob]

    with pytest.raises(ValidationError, match="at least 8"):
        await _make_use_case().execute(
            ResetPartnerPasswordCommand(
                requester_person_id=_ALICE_ID,
                new_password="short",
            ),
            uow,
        )

    uow.persons.save.assert_not_called()


async def test_reset_partner_no_partner_found() -> None:
    uow = make_mock_uow()
    alice = make_person(id=_ALICE_ID, name="Alice")
    uow.persons.get_all.return_value = [alice]

    with pytest.raises(NotFoundError, match="Partner not found"):
        await _make_use_case().execute(
            ResetPartnerPasswordCommand(
                requester_person_id=_ALICE_ID,
                new_password="newpass123",
            ),
            uow,
        )
