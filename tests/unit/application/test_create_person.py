from src.application.use_cases.create_person import (
    CreatePersonCommand,
    CreatePersonUseCase,
)
from tests.fixtures.mocks import make_mock_uow


async def test_creates_person_and_commits() -> None:
    uow = make_mock_uow()
    uow.persons.save.return_value = (
        None  # save is called, return doesn't matter for assertion
    )
    command = CreatePersonCommand(name="Alice", adjustment_account="Adjustments")

    await CreatePersonUseCase(uow).execute(command)

    uow.persons.save.assert_called_once()
    saved_person = uow.persons.save.call_args[0][0]
    assert saved_person.name == "Alice"
    assert saved_person.adjustment_account == "Adjustments"
    uow.commit.assert_called_once()


async def test_defaults_adjustment_account_to_empty() -> None:
    uow = make_mock_uow()
    command = CreatePersonCommand(name="Bob")

    await CreatePersonUseCase(uow).execute(command)

    saved_person = uow.persons.save.call_args[0][0]
    assert not saved_person.adjustment_account
