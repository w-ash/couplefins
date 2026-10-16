from src.application.use_cases.list_accounts import (
    ListAccountsCommand,
    ListAccountsUseCase,
)
from tests.fixtures.factories import ALICE, BOB, make_account, make_joint_account
from tests.fixtures.mocks import make_mock_uow


async def test_lists_every_account_by_label() -> None:
    """US-ACCOUNT-1: each label seen in uploads, and whether it is joint."""
    uow = make_mock_uow()
    bob_visa = make_account(name="Visa", owner_person_id=BOB.id)
    alice_chase = make_account(name="Chase", owner_person_id=ALICE.id)
    joint = make_joint_account("Joint Checking")
    uow.accounts.get_all.return_value = [bob_visa, joint, alice_chase]

    result = await ListAccountsUseCase().execute(ListAccountsCommand(), uow)

    assert result.accounts == [alice_chase, joint, bob_visa]


async def test_lists_nothing_before_any_upload() -> None:
    result = await ListAccountsUseCase().execute(ListAccountsCommand(), make_mock_uow())

    assert result.accounts == []
