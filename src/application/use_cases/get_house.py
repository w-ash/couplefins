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
    fetch_account_rows,
    row_shares,
)
from src.application.use_cases._shared.transactions import joint_accounts
from src.domain.constants import LINE_TAG_PREFIX
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
    SetAsideSection,
    bucket,
    owner_deposits,
    set_aside_section,
)
from src.domain.pots import compute_owner_funds, compute_pot_balances
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.domain.tags import tag_value

# The House sections, named as the response names them: every figure but
# the couple and the as-of date.
HOUSE_SECTIONS = frozenset(attrs.fields_dict(HouseFigures)) - {"persons", "as_of"}
_RECENT_ACTIVITY_LIMIT = 20


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
        budget_line=tag_value(tx.tags, LINE_TAG_PREFIX),
        amount=tx.amount,
        shares=tuple(starmap(OwnerAmount, row_shares(tx, ctx).amounts.items())),
    )


def _recent_activity(
    rows: list[Transaction], ctx: ReconciliationContext, joint: list[Account]
) -> tuple[ActivityRow, ...]:
    """The joint accounts' newest rows as activity, newest first. Rows of
    the same date order by id, so the list is stable."""
    newest = sorted(rows, key=lambda tx: (-tx.date.toordinal(), tx.id))
    account_names = {a.id: a.name for a in joint}
    return tuple(
        _activity_row(tx, ctx, account_names) for tx in newest[:_RECENT_ACTIVITY_LIMIT]
    )


def _set_aside(rows: list[Transaction], ctx: ReconciliationContext) -> SetAsideSection:
    """One bucket for each pot, the unassigned pot last, and each owner's
    deposits. The bank balances stay unknown until the owners can enter them."""
    pots = compute_pot_balances(rows)
    funds = compute_owner_funds(rows, ctx.person_ids, ctx.non_spending_categories)
    return set_aside_section(
        tuple(bucket(p.name, p.balance, is_unassigned=p.is_unassigned) for p in pots),
        owners=tuple(map(owner_deposits, funds)),
    )


@define(slots=True)
class GetHouseUseCase:
    async def execute(
        self, _command: GetHouseCommand, uow: UnitOfWorkProtocol
    ) -> GetHouseResult:
        """The House figures: real where their data exists, else the example.

        Once a joint account exists, the sections built from its rows are
        real, and only those leave `example_sections`. The example sections
        then name the couple, so every owner list keys on the same persons.
        """
        async with uow:
            joint = joint_accounts(await uow.accounts.get_all())
            if not joint:
                return GetHouseResult(
                    figures=EXAMPLE_HOUSE, example_sections=HOUSE_SECTIONS
                )
            ctx = await load_reconciliation_context(uow)
            rows = await fetch_account_rows(uow, [a.id for a in joint])
            real = {
                "set_aside": _set_aside(rows, ctx),
                "recent_activity": _recent_activity(rows, ctx, joint),
            }
            persons = tuple(HousePerson(p.id, p.name) for p in ctx.persons)
            first, second = (p.id for p in persons)
            return GetHouseResult(
                figures=evolve(example_house(first, second), persons=persons, **real),
                example_sections=HOUSE_SECTIONS.difference(real),
            )
