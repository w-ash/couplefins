import uuid

import pytest

from src.application.use_cases.update_person import (
    UpdatePersonCommand,
    UpdatePersonUseCase,
)
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import make_person
from tests.fixtures.mocks import make_mock_uow


async def test_updates_adjustment_account() -> None:
    uow = make_mock_uow()
    person = make_person(name="Alice")
    uow.persons.get_by_id.return_value = person
    uow.persons.save.return_value = make_person(
        id=person.id, name="Alice", adjustment_account="Shared Adjustments"
    )

    command = UpdatePersonCommand(id=person.id, adjustment_account="Shared Adjustments")
    result = await UpdatePersonUseCase().execute(command, uow)

    assert result.person.adjustment_account == "Shared Adjustments"
    assert result.person.name == "Alice"
    uow.persons.save.assert_called_once()
    uow.commit.assert_called_once()


async def test_updates_theme_preference() -> None:
    uow = make_mock_uow()
    person = make_person(name="Alice")
    uow.persons.get_by_id.return_value = person
    uow.persons.save.return_value = make_person(
        id=person.id, name="Alice", theme_preference="dark"
    )

    command = UpdatePersonCommand(id=person.id, theme_preference="dark")
    result = await UpdatePersonUseCase().execute(command, uow)

    assert result.person.theme_preference == "dark"
    uow.persons.save.assert_called_once()
    uow.commit.assert_called_once()


async def test_no_changes_skips_save() -> None:
    uow = make_mock_uow()
    person = make_person(name="Alice")
    uow.persons.get_by_id.return_value = person

    command = UpdatePersonCommand(id=person.id)
    result = await UpdatePersonUseCase().execute(command, uow)

    assert result.person.name == "Alice"
    uow.persons.save.assert_not_called()
    uow.commit.assert_not_called()


async def test_updates_chat_voice() -> None:
    uow = make_mock_uow()
    person = make_person(name="Alice")
    uow.persons.get_by_id.return_value = person
    uow.persons.save.return_value = make_person(
        id=person.id, name="Alice", chat_voice="standard"
    )

    command = UpdatePersonCommand(id=person.id, chat_voice="standard")
    result = await UpdatePersonUseCase().execute(command, uow)

    assert result.person.chat_voice == "standard"
    uow.persons.save.assert_called_once()
    uow.commit.assert_called_once()


async def test_person_not_found_raises() -> None:
    uow = make_mock_uow()
    uow.persons.get_by_id.return_value = None

    command = UpdatePersonCommand(
        id=uuid.uuid4(), adjustment_account="Shared Adjustments"
    )
    with pytest.raises(NotFoundError):
        await UpdatePersonUseCase().execute(command, uow)
