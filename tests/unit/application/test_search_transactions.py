import uuid

import pytest

from src.application.use_cases.search_transactions import (
    SearchTransactionsCommand,
    SearchTransactionsUseCase,
)
from src.domain.exceptions import ValidationError
from tests.fixtures.factories import make_category, make_transaction
from tests.fixtures.mocks import make_mock_uow

ALICE_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
GROUP_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_default_scope_is_all() -> None:
    uow = make_mock_uow()
    uow.transactions.get_by_date_range.return_value = [
        make_transaction(merchant="Whole Foods", payer_person_id=ALICE_ID),
    ]

    command = SearchTransactionsCommand(year=2026, month=3)
    result = await SearchTransactionsUseCase().execute(command, uow)

    assert result.total_count == 1
    uow.transactions.get_by_date_range.assert_called_once()
    uow.transactions.get_household_by_date_range.assert_not_called()


@pytest.mark.asyncio
async def test_household_scope_uses_household_fetch() -> None:
    uow = make_mock_uow()
    uow.transactions.get_household_by_date_range.return_value = [
        make_transaction(merchant="Whole Foods", payer_person_id=ALICE_ID),
    ]

    command = SearchTransactionsCommand(year=2026, month=3, scope="household")
    result = await SearchTransactionsUseCase().execute(command, uow)

    assert result.total_count == 1
    uow.transactions.get_household_by_date_range.assert_called_once()
    uow.transactions.get_by_date_range.assert_not_called()


@pytest.mark.asyncio
async def test_personal_scope_uses_person_fetch() -> None:
    uow = make_mock_uow()
    uow.transactions.get_by_person_and_date_range.return_value = [
        make_transaction(
            merchant="Whole Foods", payer_person_id=ALICE_ID, household=False
        ),
    ]

    command = SearchTransactionsCommand(
        year=2026, month=3, scope="personal", person_id=ALICE_ID
    )
    result = await SearchTransactionsUseCase().execute(command, uow)

    assert result.total_count == 1
    uow.transactions.get_by_person_and_date_range.assert_called_once()
    call_args = uow.transactions.get_by_person_and_date_range.call_args
    assert call_args.args[0] == ALICE_ID
    uow.transactions.get_by_date_range.assert_not_called()
    uow.transactions.get_household_by_date_range.assert_not_called()


@pytest.mark.asyncio
async def test_personal_scope_excludes_household_rows() -> None:
    """Personal = the user's own non-household spending; household rows they
    paid are household spending, not personal (matches the tool contract)."""
    uow = make_mock_uow()
    uow.transactions.get_by_person_and_date_range.return_value = [
        make_transaction(merchant="Rent", payer_person_id=ALICE_ID, household=True),
        make_transaction(merchant="Hobby", payer_person_id=ALICE_ID, household=False),
    ]

    command = SearchTransactionsCommand(
        year=2026, month=3, scope="personal", person_id=ALICE_ID
    )
    result = await SearchTransactionsUseCase().execute(command, uow)

    assert result.total_count == 1
    assert result.transactions[0].merchant == "Hobby"


def test_personal_scope_requires_person_id() -> None:
    with pytest.raises(ValidationError, match="person_id is required"):
        SearchTransactionsCommand(year=2026, month=3, scope="personal")


@pytest.mark.asyncio
async def test_filters_by_merchant_substring() -> None:
    uow = make_mock_uow()
    uow.transactions.get_by_date_range.return_value = [
        make_transaction(merchant="Whole Foods", payer_person_id=ALICE_ID),
        make_transaction(merchant="Trader Joe's", payer_person_id=ALICE_ID),
        make_transaction(merchant="Whole Foods Market", payer_person_id=ALICE_ID),
    ]

    command = SearchTransactionsCommand(year=2026, month=3, merchant="whole foods")
    result = await SearchTransactionsUseCase().execute(command, uow)

    assert result.total_count == 2
    assert all("Whole Foods" in t.merchant for t in result.transactions)


@pytest.mark.asyncio
async def test_filters_by_category_group() -> None:
    uow = make_mock_uow()
    uow.transactions.get_by_date_range.return_value = [
        make_transaction(category="Groceries", payer_person_id=ALICE_ID),
        make_transaction(category="Dining Out", payer_person_id=ALICE_ID),
    ]
    uow.categories.get_all.return_value = [
        make_category(name="Groceries", group_id=GROUP_ID),
        make_category(name="Dining Out", group_id=uuid.uuid4()),
    ]

    command = SearchTransactionsCommand(year=2026, month=3, category_group_id=GROUP_ID)
    result = await SearchTransactionsUseCase().execute(command, uow)

    assert result.total_count == 1
    assert result.transactions[0].category == "Groceries"


@pytest.mark.asyncio
async def test_limits_results() -> None:
    uow = make_mock_uow()
    uow.transactions.get_by_date_range.return_value = [
        make_transaction(merchant=f"Store {i}", payer_person_id=ALICE_ID)
        for i in range(30)
    ]

    command = SearchTransactionsCommand(year=2026, month=3, limit=5)
    result = await SearchTransactionsUseCase().execute(command, uow)

    assert result.total_count == 30
    assert len(result.transactions) == 5


@pytest.mark.asyncio
async def test_empty_results() -> None:
    uow = make_mock_uow()
    uow.transactions.get_by_date_range.return_value = []

    command = SearchTransactionsCommand(year=2026, month=3, merchant="Nothing")
    result = await SearchTransactionsUseCase().execute(command, uow)

    assert result.total_count == 0
    assert result.transactions == []


@pytest.mark.asyncio
async def test_filters_by_tag() -> None:
    uow = make_mock_uow()
    # Tag filtering is delegated to the repository's server-side (JSONB) filter;
    # the mock returns the already-filtered rows.
    uow.transactions.get_by_date_range.return_value = [
        make_transaction(merchant="Coffee Shop", tags=("discuss",)),
        make_transaction(merchant="Bakery", tags=("discuss",)),
    ]

    command = SearchTransactionsCommand(year=2026, month=3, tag="discuss")
    result = await SearchTransactionsUseCase().execute(command, uow)

    assert result.total_count == 2
    # The tag is pushed down to the repo query, not filtered in memory.
    assert uow.transactions.get_by_date_range.call_args.kwargs["tags"] == ("discuss",)


@pytest.mark.asyncio
async def test_tag_filter_pushed_to_repo_per_scope() -> None:
    """The tag is threaded into each scope's repo query via its tags= kwarg."""
    uow = make_mock_uow()
    uow.transactions.get_household_by_date_range.return_value = [
        make_transaction(merchant="Coffee Shop", tags=("discuss",)),
    ]

    command = SearchTransactionsCommand(
        year=2026, month=3, scope="household", tag="discuss"
    )
    result = await SearchTransactionsUseCase().execute(command, uow)

    assert result.total_count == 1
    assert result.transactions[0].merchant == "Coffee Shop"
    call = uow.transactions.get_household_by_date_range.call_args
    assert call.kwargs["tags"] == ("discuss",)
