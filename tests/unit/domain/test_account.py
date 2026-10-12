import uuid

import pytest

from src.domain.entities.account import Account


def test_personal_account_has_an_owner() -> None:
    owner = uuid.uuid4()

    account = Account(
        id=uuid.uuid4(), name="Chase", kind="personal", owner_person_id=owner
    )

    assert account.owner_person_id == owner


def test_joint_account_has_no_owner() -> None:
    account = Account(id=uuid.uuid4(), name="House", kind="joint", owner_person_id=None)

    assert account.owner_person_id is None


def test_personal_account_without_owner_is_rejected() -> None:
    with pytest.raises(ValueError, match="personal account must have an owner"):
        Account(id=uuid.uuid4(), name="Chase", kind="personal", owner_person_id=None)


def test_joint_account_with_owner_is_rejected() -> None:
    with pytest.raises(ValueError, match="joint account none"):
        Account(
            id=uuid.uuid4(), name="House", kind="joint", owner_person_id=uuid.uuid4()
        )
