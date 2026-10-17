"""Pot balances and owner funds over the joint accounts' rows (v1.15.3)."""

from collections.abc import Mapping
from decimal import Decimal
from uuid import UUID

import attrs
import pytest

from src.domain.constants import UNASSIGNED_POT
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import InvariantViolationError
from src.domain.pots import (
    OwnerFunds,
    PotBalance,
    compute_owner_funds,
    compute_pot_balances,
)
from tests.fixtures.factories import ALICE, BOB, COUPLE_IDS, make_transaction

NON_SPENDING = frozenset({"Transfer"})


def _row(
    amount: str,
    *tags: str,
    category: str = "Home Improvement",
    depositor: UUID | None = None,
    owner_shares: Mapping[UUID, int] | None = None,
    is_excluded: bool = False,
) -> Transaction:
    """A joint row."""
    return make_transaction(
        joint=True,
        amount=Decimal(amount),
        tags=tags,
        category=category,
        depositor_person_id=depositor,
        owner_shares=owner_shares,
        is_excluded=is_excluded,
    )


def _deposit(amount: str, person: UUID, *tags: str) -> Transaction:
    return _row(amount, *tags, category="Transfer", depositor=person)


def _funds(rows: list[Transaction]) -> dict[UUID, OwnerFunds]:
    return {f.person_id: f for f in compute_owner_funds(rows, COUPLE_IDS, NON_SPENDING)}


# A month of a joint account: both owners deposit (Bob partly a gift), bills
# are paid from two pots, a refund comes back, and money moves between pots.
MONTH = [
    _deposit("1600.00", ALICE.id, "pot:bills"),
    _deposit("1000.00", BOB.id, "pot:bills"),
    _deposit("500.00", BOB.id, "pot:renovation", "source:gift"),
    _row("-1200.00", "pot:bills", "line:mortgage", category="Mortgage"),
    _row("-300.00", "pot:renovation", owner_shares={ALICE.id: 60, BOB.id: 40}),
    _row("40.00", "pot:renovation"),
    _row("-400.00", "pot:bills", category="Transfer"),
    _row("400.00", "pot:renovation", category="Transfer"),
    _row("-25.00", category="Bank Fees"),
]


class TestPotBalances:
    def test_each_pot_nets_its_rows(self) -> None:
        assert compute_pot_balances(MONTH) == (
            PotBalance("bills", Decimal("2600.00"), Decimal("1600.00")),
            PotBalance("renovation", Decimal("940.00"), Decimal("300.00")),
            PotBalance(UNASSIGNED_POT, Decimal(0), Decimal("25.00")),
        )
        assert [p.balance for p in compute_pot_balances(MONTH)] == [
            Decimal("1000.00"),
            Decimal("640.00"),
            Decimal("-25.00"),
        ]

    def test_the_balances_sum_to_the_rows(self) -> None:
        pots = compute_pot_balances(MONTH)

        assert sum(p.balance for p in pots) == sum(tx.amount for tx in MONTH)

    def test_a_pot_to_pot_transfer_moves_money_but_nets_to_zero(self) -> None:
        legs = [
            _row("-400.00", "pot:bills", category="Transfer"),
            _row("400.00", "pot:renovation", category="Transfer"),
        ]

        bills, renovation = compute_pot_balances(legs)

        assert (bills.balance, renovation.balance) == (
            Decimal("-400.00"),
            Decimal("400.00"),
        )
        assert bills.balance + renovation.balance == 0

    def test_pots_sort_by_name_with_the_unassigned_pot_last(self) -> None:
        rows = [_row("-1.00"), _row("-1.00", "pot:zoo"), _row("-1.00", "pot:attic")]

        pots = compute_pot_balances(rows)

        assert [p.name for p in pots] == ["attic", "zoo", UNASSIGNED_POT]
        assert [p.is_unassigned for p in pots] == [False, False, True]

    def test_a_pot_tag_cannot_name_the_unassigned_pot(self) -> None:
        rows = [_row("-1.00"), _row("-2.00", "pot:unassigned")]

        assert [(p.name, p.balance) for p in compute_pot_balances(rows)] == [
            ("unassigned", Decimal("-2.00")),
            (UNASSIGNED_POT, Decimal("-1.00")),
        ]

    def test_an_excluded_row_counts_in_no_pot(self) -> None:
        rows = [
            _row("-90.00", "pot:bills", is_excluded=True),
            _deposit("500.00", ALICE.id, "pot:attic"),
            _row("40.00", "pot:attic", is_excluded=True),
        ]

        assert compute_pot_balances(rows) == (
            PotBalance("attic", Decimal("500.00"), Decimal(0)),
        )

    def test_no_rows_no_pots(self) -> None:
        assert compute_pot_balances([]) == ()


class TestOwnerFunds:
    def test_unspent_is_deposits_less_the_share_of_payments(self) -> None:
        alice, bob = (_funds(MONTH)[p] for p in COUPLE_IDS)

        # The mortgage 1200 at 50/50, the renovation 300 at 60/40, the bank
        # fee 25 at 50/50, less the refund 40 at 50/50; the transfer counts
        # for neither. Alice: 600 + 180 + 12.50 - 20; Bob: 600 + 120 + 12.50 - 20.
        assert (alice.share_of_payments, bob.share_of_payments) == (
            Decimal("772.50"),
            Decimal("712.50"),
        )
        assert (alice.unspent, bob.unspent) == (Decimal("827.50"), Decimal("787.50"))

    def test_both_unspent_are_all_deposits_less_all_spending(self) -> None:
        funds = _funds(MONTH)
        deposits = Decimal("3100.00")
        spending = (
            Decimal("1200.00") + Decimal("300.00") - Decimal("40.00") + Decimal("25.00")
        )

        assert sum(f.unspent for f in funds.values()) == deposits - spending

    def test_a_gift_deposit_is_a_gift(self) -> None:
        bob = _funds(MONTH)[BOB.id]

        assert (bob.own_deposits, bob.gift_deposits, bob.deposits) == (
            Decimal("1000.00"),
            Decimal("500.00"),
            Decimal("1500.00"),
        )

    @pytest.mark.parametrize("tags", [(), ("source:own",), ("source:inheritance",)])
    def test_any_other_deposit_is_the_depositors_own(
        self, tags: tuple[str, ...]
    ) -> None:
        alice = _funds([_deposit("100.00", ALICE.id, *tags)])[ALICE.id]

        assert (alice.own_deposits, alice.gift_deposits) == (Decimal("100.00"), 0)

    def test_a_transfer_is_never_a_payment(self) -> None:
        funds = _funds([_row("-400.00", "pot:bills", category="Transfer")])

        assert [f.share_of_payments for f in funds.values()] == [0, 0]

    def test_money_in_with_no_depositor_in_a_spending_category_is_a_refund(
        self,
    ) -> None:
        funds = _funds([_row("-100.00"), _row("75.00")])

        assert [f.share_of_payments for f in funds.values()] == [
            Decimal("12.50"),
            Decimal("12.50"),
        ]

    def test_an_excluded_row_changes_no_owners_funds(self) -> None:
        rows = [
            _deposit("1000.00", ALICE.id, "source:gift"),
            _row("-90.00", is_excluded=True),
            _row("75.00", is_excluded=True),
            attrs.evolve(_deposit("500.00", BOB.id), is_excluded=True),
        ]

        alice, bob = (_funds(rows)[p] for p in COUPLE_IDS)

        assert (alice.gift_deposits, alice.share_of_payments) == (
            Decimal("1000.00"),
            0,
        )
        assert (bob.deposits, bob.share_of_payments) == (0, 0)

    def test_money_in_with_no_depositor_is_nobodys_deposit(self) -> None:
        funds = _funds([_row("1500.00", category="Transfer")])

        assert [f.deposits for f in funds.values()] == [0, 0]

    def test_one_entry_for_each_owner_in_person_order(self) -> None:
        reversed_ids = (BOB.id, ALICE.id)

        funds = compute_owner_funds([], reversed_ids, NON_SPENDING)

        assert [f.person_id for f in funds] == list(reversed_ids)
        assert all(f.unspent == 0 for f in funds)

    def test_a_depositor_outside_the_couple_raises(self) -> None:
        stranger = make_transaction().payer_person_id
        assert stranger is not None

        with pytest.raises(InvariantViolationError):
            _funds([_deposit("10.00", stranger)])
