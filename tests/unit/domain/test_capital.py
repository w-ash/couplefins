"""Owner capital from `share:` rows (US-HOUSE-10): which rows credit whom,
by how much, and how the credits add up to capital and percents."""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
import uuid

import attrs
import pytest

from src.domain.capital import CapitalAccounts, capital_accounts, share_kind
from src.domain.entities.co_owned_asset import CONTRIBUTION_KINDS, CoOwnedAsset
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import InvariantViolationError
from src.domain.house import OwnerAmount
from src.domain.month_key import months_through
from tests.fixtures.factories import (
    ALICE,
    BOB,
    COUPLE_IDS,
    make_co_owned_asset,
    make_share_transaction,
    make_transaction,
)

ASSET = make_co_owned_asset(repair_threshold=Decimal("500.00"))
THROUGH = (2026, 12)


def _accounts(
    rows: Iterable[Transaction], asset: CoOwnedAsset = ASSET
) -> CapitalAccounts:
    return capital_accounts(rows, COUPLE_IDS, asset, THROUGH)


def _credits(tx: Transaction, asset: CoOwnedAsset = ASSET) -> tuple[Decimal, Decimal]:
    """Each owner's credit from the one row: their capital at the end."""
    alice, bob = _accounts([tx], asset).history[-1].owners
    return alice.capital, bob.capital


class TestShareKind:
    @pytest.mark.parametrize("kind", CONTRIBUTION_KINDS)
    def test_names_each_kind(self, kind: str) -> None:
        assert share_kind(make_share_transaction(kind)) == kind

    def test_first_share_tag_wins(self) -> None:
        tx = make_share_transaction("repair", tags=("share:closing",))

        assert share_kind(tx) == "closing"

    @pytest.mark.parametrize(
        "tags",
        [(), ("shared",), ("share:none",), ("share:roof",), ("line:closing",)],
    )
    def test_no_kind_without_a_known_share_tag(self, tags: tuple[str, ...]) -> None:
        assert share_kind(make_transaction(tags=tags)) is None


class TestCredits:
    def test_a_split_expense_credits_each_owner_their_share(self) -> None:
        tx = make_share_transaction("closing", Decimal("-1000.00"), payer_percentage=60)

        assert _credits(tx) == (Decimal("600.00"), Decimal("400.00"))

    @pytest.mark.parametrize("payer_percentage", [0, 33, 50, 67, 100])
    @pytest.mark.parametrize("amount", ["-100.01", "-0.03", "77.77"])
    def test_owner_credits_sum_to_the_amount_exactly(
        self, payer_percentage: int, amount: str
    ) -> None:
        tx = make_share_transaction(
            "insurance", Decimal(amount), payer_percentage=payer_percentage
        )

        assert sum(_credits(tx)) == -tx.amount

    @pytest.mark.parametrize("tags", [("s100",), ("household",)])
    def test_a_personal_row_the_payer_keeps_credits_the_payer_in_full(
        self, tags: tuple[str, ...]
    ) -> None:
        tx = make_share_transaction(
            "agreed-work",
            Decimal("-250.00"),
            payer_person_id=BOB.id,
            payer_percentage=100,
            tags=tags,
        )

        assert _credits(tx) == (Decimal(0), Decimal("250.00"))

    @pytest.mark.parametrize(
        ("alice", "expected"),
        [
            (70, (Decimal("630.00"), Decimal("270.00"))),
            # A missed payment Alice covered for both (US-HOUSE-11).
            (100, (Decimal("900.00"), Decimal(0))),
        ],
    )
    def test_a_joint_row_credits_by_its_owner_shares(
        self, alice: int, expected: tuple[Decimal, Decimal]
    ) -> None:
        tx = make_share_transaction(
            "loan-principal",
            Decimal("-900.00"),
            joint=True,
            owner_shares={ALICE.id: alice, BOB.id: 100 - alice},
        )

        assert _credits(tx) == expected

    def test_a_refund_reduces_the_credit(self) -> None:
        """Signed convention; reversible once the owners decide (US-HOUSE-10)."""
        refund = make_share_transaction("insurance", Decimal("120.00"))

        assert _credits(refund) == (Decimal("-60.00"), Decimal("-60.00"))

    @pytest.mark.parametrize(
        ("amount", "counts"),
        [
            ("-499.99", False),
            ("-500.00", True),
            ("-500.01", True),
            ("499.99", False),
            ("500.00", True),
        ],
    )
    def test_a_repair_counts_from_the_threshold_up_in_absolute_amount(
        self, amount: str, counts: bool
    ) -> None:
        tx = make_share_transaction("repair", Decimal(amount))

        assert bool(_accounts([tx]).by_kind) is counts

    @pytest.mark.parametrize(
        "tags", [("share:none",), ("share:roof",), ("shared",), ()]
    )
    def test_none_unknown_and_untagged_rows_credit_nothing(
        self, tags: tuple[str, ...]
    ) -> None:
        tx = make_transaction(
            tags=tags, payer_person_id=ALICE.id, amount=Decimal("-80.00")
        )

        assert _accounts([tx]).by_kind == {}
        assert _credits(tx) == (Decimal(0), Decimal(0))

    def test_a_kind_the_asset_does_not_list_credits_nothing(self) -> None:
        asset = make_co_owned_asset(qualifying_kinds=frozenset({"closing"}))

        assert _credits(make_share_transaction("insurance"), asset) == (0, 0)

    def test_an_asset_with_no_qualifying_kind_credits_nothing(self) -> None:
        asset = make_co_owned_asset(qualifying_kinds=frozenset())
        rows = [make_share_transaction(kind) for kind in CONTRIBUTION_KINDS]

        accounts = _accounts(rows, asset)

        assert accounts.by_kind == {}
        assert [o.capital for o in accounts.history[-1].owners] == [0, 0]

    @pytest.mark.parametrize(
        "flags",
        [
            {"is_excluded": True},
            {"is_settlement": True},
            {"household": False},
            {"category": "Credit Card Payment"},
        ],
    )
    def test_the_tag_is_the_only_lever(self, flags: dict[str, object]) -> None:
        """Exclusion, settlement, household, and category kind do not matter."""
        tx = attrs.evolve(make_share_transaction("closing", Decimal("-50.00")), **flags)

        assert _credits(tx) == (Decimal("25.00"), Decimal("25.00"))

    def test_a_row_naming_another_person_fails(self) -> None:
        tx = make_share_transaction("closing", payer_person_id=uuid.uuid4())

        with pytest.raises(InvariantViolationError):
            _accounts([tx])


ROWS = (
    make_share_transaction("closing", Decimal("-3000.00"), date=date(2025, 11, 20)),
    make_share_transaction(
        "loan-interest",
        Decimal("-400.00"),
        date=date(2026, 1, 1),
        payer_person_id=BOB.id,
        payer_percentage=100,
        tags=("s100",),
    ),
    make_share_transaction(
        "insurance",
        Decimal("-300.00"),
        date=date(2026, 1, 31),
        joint=True,
        owner_shares={ALICE.id: 20, BOB.id: 80},
    ),
    make_share_transaction("insurance", Decimal("30.00"), date=date(2026, 3, 2)),
    make_share_transaction("repair", Decimal("-100.00"), date=date(2026, 3, 5)),
    make_transaction(tags=("shared",), date=date(2026, 2, 1)),
)


class TestHistory:
    def test_each_month_holds_the_credits_through_it(self) -> None:
        history = capital_accounts(ROWS, COUPLE_IDS, ASSET, (2026, 4)).history

        assert [(p.year, p.month) for p in history] == list(
            months_through((2025, 11), (2026, 4))
        )
        assert [tuple(o.capital for o in p.owners) for p in history] == [
            (Decimal("1500.00"), Decimal("1500.00")),
            (Decimal("1500.00"), Decimal("1500.00")),
            (Decimal("1560.00"), Decimal("2140.00")),
            (Decimal("1560.00"), Decimal("2140.00")),
            # A refund takes 15 off each; the repair is under the threshold.
            (Decimal("1545.00"), Decimal("2125.00")),
            (Decimal("1545.00"), Decimal("2125.00")),
        ]

    def test_percents_sum_to_exactly_100(self) -> None:
        history = capital_accounts(ROWS, COUPLE_IDS, ASSET, (2026, 4)).history

        for point in history:
            assert sum((o.percent for o in point.owners), Decimal(0)) == 100
        assert [o.percent for o in history[-1].owners] == [
            Decimal("42.1"),
            Decimal("57.9"),
        ]

    def test_without_credits_it_is_one_zero_point(self) -> None:
        history = capital_accounts(
            [make_transaction(tags=("shared",))], COUPLE_IDS, ASSET, (2026, 4)
        ).history

        assert [(p.year, p.month) for p in history] == [(2026, 4)]
        assert [(o.capital, o.percent) for o in history[0].owners] == [(0, 0), (0, 0)]

    def test_a_later_credit_counts_nowhere_yet(self) -> None:
        accounts = capital_accounts(ROWS, COUPLE_IDS, ASSET, (2025, 10))

        assert [(p.year, p.month) for p in accounts.history] == [(2025, 10)]
        assert [o.capital for o in accounts.history[0].owners] == [0, 0]
        assert accounts.by_kind == {}

    def test_owners_follow_the_given_order(self) -> None:
        history = capital_accounts(ROWS, (BOB.id, ALICE.id), ASSET, THROUGH).history

        assert [o.person_id for o in history[-1].owners] == [BOB.id, ALICE.id]


class TestByKind:
    def test_each_kind_holds_each_owners_credits_in_kind_order(self) -> None:
        by_kind = _accounts(ROWS).by_kind

        assert by_kind == {
            "closing": (
                OwnerAmount(ALICE.id, Decimal("1500.00")),
                OwnerAmount(BOB.id, Decimal("1500.00")),
            ),
            "loan-interest": (
                OwnerAmount(ALICE.id, Decimal(0)),
                OwnerAmount(BOB.id, Decimal("400.00")),
            ),
            "insurance": (
                OwnerAmount(ALICE.id, Decimal("45.00")),
                OwnerAmount(BOB.id, Decimal("225.00")),
            ),
        }
        assert list(by_kind) == ["closing", "loan-interest", "insurance"]

    def test_the_kinds_sum_to_each_owners_capital(self) -> None:
        accounts = _accounts(ROWS)

        for share in accounts.history[-1].owners:
            assert share.capital == sum(
                (
                    a.amount
                    for amounts in accounts.by_kind.values()
                    for a in amounts
                    if a.person_id == share.person_id
                ),
                Decimal(0),
            )


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ((2025, 11), (2026, 2), ((2025, 11), (2025, 12), (2026, 1), (2026, 2))),
        ((2026, 3), (2026, 3), ((2026, 3),)),
        ((2026, 4), (2026, 3), ()),
    ],
)
def test_months_through_counts_across_years(
    start: tuple[int, int],
    end: tuple[int, int],
    expected: tuple[tuple[int, int], ...],
) -> None:
    assert months_through(start, end) == expected
