from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.domain.spending_lens import (
    AllRowsLens,
    HouseholdLens,
    PersonalLens,
    SpendingLens,
    SplitLens,
    compute_breakdowns,
    select,
    source_split,
    total_spending,
)
from tests.fixtures.factories import ALICE, BOB, make_transaction

FOOD = uuid4()
LOOKUP = {"Dining Out": (FOOD, "Food & Dining"), "Groceries": (FOOD, "Food & Dining")}


@pytest.mark.parametrize(
    ("household", "payer_percentage", "category", "expected"),
    [
        (True, 50, "Dining Out", True),
        (True, 100, "Dining Out", True),
        (False, 100, "Dining Out", False),
        (False, 100, "Groceries", True),  # include_personal opt-in
        (False, 0, "Groceries", True),
    ],
)
def test_household_lens_relevance(
    household: bool, payer_percentage: int, category: str, expected: bool
) -> None:
    lens = HouseholdLens(frozenset({"Groceries"}))
    tx = make_transaction(
        household=household, payer_percentage=payer_percentage, category=category
    )
    assert lens.is_relevant(tx) is expected


@pytest.mark.parametrize(
    ("household", "payer_percentage", "viewer", "expected"),
    [
        (True, 50, BOB.id, True),
        # partner's own concert ticket tagged household: household-only
        (True, 100, BOB.id, False),
        (True, 100, ALICE.id, True),
        # household spotted (s0): $0 for the payer
        (True, 0, ALICE.id, False),
        (True, 0, BOB.id, True),
        (False, 100, ALICE.id, True),
        (False, 100, BOB.id, False),
        (False, 50, BOB.id, True),
        (False, 0, ALICE.id, False),
        (False, 0, BOB.id, True),
    ],
)
def test_personal_lens_relevance_is_nonzero_share(
    household: bool, payer_percentage: int, viewer: UUID, expected: bool
) -> None:
    tx = make_transaction(
        household=household, payer_percentage=payer_percentage, payer_person_id=ALICE.id
    )
    assert PersonalLens(viewer).is_relevant(tx) is expected


@pytest.mark.parametrize(
    "lens",
    [HouseholdLens(), PersonalLens(ALICE.id), SplitLens(), AllRowsLens()],
    ids=type,
)
@pytest.mark.parametrize("flag", ["is_excluded", "is_settlement"])
def test_every_lens_layers_on_reconciliation_relevance(
    lens: SpendingLens, flag: str
) -> None:
    tx = make_transaction(household=True, payer_person_id=ALICE.id, **{flag: True})
    assert lens.is_relevant(tx) is False


def test_split_lens_is_the_settlement_universe() -> None:
    assert SplitLens().is_relevant(
        make_transaction(household=False, payer_percentage=0)
    )
    assert not SplitLens().is_relevant(
        make_transaction(household=True, payer_percentage=100)
    )


@pytest.mark.parametrize(
    ("household", "payer_percentage"),
    [(True, 50), (True, 100), (False, 100), (False, 0)],
)
def test_all_rows_lens_admits_every_relevant_row(
    household: bool, payer_percentage: int
) -> None:
    tx = make_transaction(household=household, payer_percentage=payer_percentage)
    assert AllRowsLens().is_relevant(tx)


def test_all_rows_lens_nets_refunds_and_never_reads_below_household() -> None:
    txs = [
        make_transaction(amount=Decimal("-500.00"), household=True),
        make_transaction(amount=Decimal("50.00"), household=True),
        make_transaction(
            amount=Decimal("-100.00"), household=False, payer_percentage=100
        ),
    ]
    assert total_spending(HouseholdLens(), txs) == Decimal("450.00")
    assert total_spending(AllRowsLens(), txs) == Decimal("550.00")
    assert total_spending(AllRowsLens(), txs) >= total_spending(HouseholdLens(), txs)


def test_all_rows_breakdown_partitions_into_household_and_personal() -> None:
    txs = [
        make_transaction(
            category="Groceries", amount=Decimal("-100.00"), household=True
        ),
        make_transaction(
            category="Dining Out",
            amount=Decimal("-60.00"),
            household=False,
            payer_percentage=100,
            payer_person_id=ALICE.id,
        ),
        make_transaction(
            category="Dining Out",
            amount=Decimal("-30.00"),
            household=False,
            payer_percentage=0,
            payer_person_id=BOB.id,
            tags=("alice",),
        ),
    ]
    breakdowns = compute_breakdowns(AllRowsLens(), txs, LOOKUP)
    household, personal = source_split(breakdowns)
    assert (household, personal) == (Decimal("100.00"), Decimal("90.00"))
    assert household + personal == total_spending(AllRowsLens(), txs)
    dining = next(c for c in breakdowns[0].categories if c.category == "Dining Out")
    assert dining.personal_amounts == {
        ALICE.id: Decimal("60.00"),
        BOB.id: Decimal("30.00"),
    }


def test_contribution_is_signed_under_every_lens() -> None:
    expense = make_transaction(amount=Decimal("-100.00"), payer_person_id=ALICE.id)
    refund = make_transaction(amount=Decimal("40.00"), payer_person_id=ALICE.id)
    assert (
        HouseholdLens().contribution(expense),
        HouseholdLens().contribution(refund),
    ) == (Decimal("100.00"), Decimal("-40.00"))
    assert (
        PersonalLens(BOB.id).contribution(expense),
        PersonalLens(BOB.id).contribution(refund),
    ) == (Decimal("50.00"), Decimal("-20.00"))
    assert SplitLens().contribution(refund) == Decimal("-40.00")
    assert AllRowsLens().contribution(refund) == Decimal("-40.00")


def test_personal_owner_is_payer_viewer_or_nobody() -> None:
    tx = make_transaction(
        household=False, category="Groceries", payer_person_id=ALICE.id
    )
    assert HouseholdLens(frozenset({"Groceries"})).personal_owner(tx) == ALICE.id
    assert HouseholdLens().personal_owner(tx) is None
    assert PersonalLens(BOB.id).personal_owner(tx) == BOB.id
    assert SplitLens().personal_owner(tx) is None
    assert AllRowsLens().personal_owner(tx) == ALICE.id


def test_breakdowns_attribute_buckets_by_lens() -> None:
    txs = [
        make_transaction(
            category="Groceries",
            amount=Decimal("-100.00"),
            household=True,
            payer_person_id=ALICE.id,
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal("-60.00"),
            household=False,
            payer_percentage=100,
            payer_person_id=ALICE.id,
        ),
        make_transaction(
            category="Groceries",
            amount=Decimal("-30.00"),
            household=False,
            payer_percentage=0,
            payer_person_id=BOB.id,
            tags=("alice",),
        ),
    ]
    household = compute_breakdowns(
        HouseholdLens(frozenset({"Groceries"})), txs, LOOKUP
    )[0]
    cat = household.categories[0]
    assert cat.total_amount == Decimal("190.00")
    assert cat.household_amount == Decimal("100.00")
    # payer-keyed: Bob fronted the spotted row
    assert cat.personal_amounts == {
        ALICE.id: Decimal("60.00"),
        BOB.id: Decimal("30.00"),
    }

    alice_bd = compute_breakdowns(PersonalLens(ALICE.id), txs, LOOKUP)[0]
    alice = alice_bd.categories[0]
    assert alice.total_amount == Decimal("140.00")
    assert alice.household_amount == Decimal("50.00")
    # viewer-keyed: the spot is Alice's spending
    assert alice.personal_amounts == {ALICE.id: Decimal("90.00")}
    assert source_split([alice_bd]) == (Decimal("50.00"), Decimal("90.00"))


def test_unattributed_personal_row_keeps_total_but_no_bucket() -> None:
    txs = [
        make_transaction(
            category="Dining Out",
            amount=Decimal("-50.00"),
            household=False,
            payer_person_id=ALICE.id,
        )
    ]
    bd = compute_breakdowns(HouseholdLens(frozenset({"Dining Out"})), txs, LOOKUP)[0]
    cat = bd.categories[0]
    assert (cat.total_amount, cat.household_amount) == (Decimal("50.00"), Decimal(0))
    assert cat.personal_amounts == {ALICE.id: Decimal("50.00")}
    assert compute_breakdowns(HouseholdLens(), txs, LOOKUP) == []


def test_select_and_total_agree() -> None:
    txs = [
        make_transaction(amount=Decimal("-80.00"), payer_person_id=ALICE.id),
        make_transaction(amount=Decimal("20.00"), payer_person_id=ALICE.id),
        make_transaction(amount=Decimal("-5.00"), is_excluded=True),
    ]
    assert len(select(HouseholdLens(), txs)) == 2
    assert total_spending(HouseholdLens(), txs) == Decimal("60.00")
    assert total_spending(PersonalLens(BOB.id), txs) == Decimal("30.00")
