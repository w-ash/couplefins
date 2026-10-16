from itertools import starmap
from uuid import UUID

import attrs
from attrs import define, evolve

from src.application.use_cases._shared.house_example import (
    EXAMPLE_HOUSE,
    example_house,
)
from src.application.use_cases._shared.reconciliation_context import (
    ReconciliationContext,
    load_reconciliation_context,
)
from src.application.use_cases._shared.transaction_reads import (
    fetch_joint_rows,
    row_shares,
)
from src.application.use_cases._shared.transactions import joint_accounts
from src.domain.entities.account import Account
from src.domain.entities.category_group import GroupKind
from src.domain.entities.transaction import Transaction
from src.domain.filters import depositor_of
from src.domain.house import (
    ActivityKind,
    ActivityRow,
    HouseFigures,
    HousePerson,
    OwnerAmount,
)
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

# The House sections, named as the response names them: every figure but
# the couple and the as-of date.
HOUSE_SECTIONS = frozenset(attrs.fields_dict(HouseFigures)) - {"persons", "as_of"}
_RECENT_ACTIVITY_LIMIT = 20
# A row's budget line is the value of its first `line:` tag.
_BUDGET_LINE_PREFIX = "line:"


@define(frozen=True, slots=True)
class GetHouseCommand:
    """Parameterless — exists for API uniformity."""


@define(frozen=True, slots=True)
class GetHouseResult:
    """Every House figure, precomputed — the UI renders, never derives.

    ``example_sections`` names the sections whose figures are still the
    fixed example payload; the page says so until real figures replace them.
    """

    figures: HouseFigures
    example_sections: frozenset[str]


def _activity_kind(tx: Transaction, kind: GroupKind | None) -> ActivityKind:
    """A deposit names its depositor; otherwise a transfer-kind row is a
    transfer, and money in or out is a refund or a payment."""
    if depositor_of(tx) is not None:
        return "deposit"
    if kind == "transfer":
        return "transfer"
    return "refund" if tx.amount > 0 else "payment"


def _budget_line(tx: Transaction) -> str | None:
    return next(
        (
            tag.removeprefix(_BUDGET_LINE_PREFIX)
            for tag in tx.tags
            if tag.startswith(_BUDGET_LINE_PREFIX)
        ),
        None,
    )


def _activity_row(
    tx: Transaction, ctx: ReconciliationContext, account_names: dict[UUID, str]
) -> ActivityRow:
    """One joint row as House activity. Its shares are the row's split: a
    deposit's depositor alone, none for a transfer."""
    return ActivityRow(
        id=tx.id,
        date=tx.date,
        account_name=account_names.get(tx.account_id, tx.account),
        person_id=tx.depositor_person_id,
        kind=_activity_kind(tx, ctx.category_kinds.get(tx.category)),
        budget_line=_budget_line(tx),
        amount=tx.amount,
        shares=tuple(starmap(OwnerAmount, row_shares(tx, ctx).amounts.items())),
    )


async def _recent_activity(
    uow: UnitOfWorkProtocol, joint: list[Account]
) -> tuple[tuple[HousePerson, ...], tuple[ActivityRow, ...]]:
    """The couple and the joint accounts' newest rows as activity."""
    ctx = await load_reconciliation_context(uow)
    rows = await fetch_joint_rows(uow, [a.id for a in joint], _RECENT_ACTIVITY_LIMIT)
    account_names = {a.id: a.name for a in joint}
    persons = tuple(HousePerson(p.id, p.name) for p in ctx.persons)
    return persons, tuple(_activity_row(tx, ctx, account_names) for tx in rows)


@define(slots=True)
class GetHouseUseCase:
    async def execute(
        self, _command: GetHouseCommand, uow: UnitOfWorkProtocol
    ) -> GetHouseResult:
        """The House figures: real where their data exists, else the example.

        Recent activity is real once a joint account exists. The example
        sections then name the couple, so every owner list keys on the same
        persons.
        """
        async with uow:
            joint = joint_accounts(await uow.accounts.get_all())
            if not joint:
                return GetHouseResult(
                    figures=EXAMPLE_HOUSE, example_sections=HOUSE_SECTIONS
                )
            persons, activity = await _recent_activity(uow, joint)
            first, second = (p.id for p in persons)
            return GetHouseResult(
                figures=evolve(
                    example_house(first, second),
                    persons=persons,
                    recent_activity=activity,
                ),
                example_sections=HOUSE_SECTIONS - {"recent_activity"},
            )
