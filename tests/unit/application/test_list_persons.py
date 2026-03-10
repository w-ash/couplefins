from src.application.use_cases.list_persons import list_persons
from tests.fixtures.factories import make_person
from tests.fixtures.mocks import make_mock_uow


async def test_returns_all_persons() -> None:
    uow = make_mock_uow()
    persons = [make_person(name="Alice"), make_person(name="Bob")]
    uow.persons.get_all.return_value = persons

    result = await list_persons(uow)

    assert result.persons == persons
    uow.persons.get_all.assert_called_once()


async def test_returns_empty_list_when_no_persons() -> None:
    uow = make_mock_uow()
    uow.persons.get_all.return_value = []

    result = await list_persons(uow)

    assert result.persons == []
