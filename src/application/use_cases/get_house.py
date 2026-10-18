import datetime
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
    HouseRows,
    fetch_house_rows,
    row_shares,
)
from src.application.use_cases._shared.transactions import joint_accounts
from src.domain.capital import capital_accounts
from src.domain.constants import LINE_TAG_PREFIX
from src.domain.entities.account import Account
from src.domain.entities.category_group import GroupKind
from src.domain.entities.co_owned_asset import CoOwnedAsset
from src.domain.entities.transaction import Transaction
from src.domain.filters import depositor_of
from src.domain.house import (
    ActivityKind,
    ActivityRow,
    HouseFigures,
    HousePerson,
    LoanFigures,
    ObligationFigures,
    OwnerAmount,
    SetAsideSection,
    bucket,
    owner_deposits,
    put_in_section,
    set_aside_section,
    shares_section,
    with_shortfalls,
)
from src.domain.loans import loan_figures
from src.domain.obligations import obligation_figures, recently_paid, upcoming
from src.domain.pots import (
    OwnerFunds,
    PotBalance,
    compute_owner_funds,
    compute_pot_balances,
)
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.domain.tags import tag_value

# The House sections, named as the response names them: every figure but
# the couple and the as-of date.
HOUSE_SECTIONS = frozenset(attrs.fields_dict(HouseFigures)) - {"persons", "as_of"}
_RECENT_ACTIVITY_LIMIT = 20


@define(frozen=True, slots=True)
class GetHouseCommand:
    """``as_of`` is the date of the real figures: today (UTC) when None."""

    as_of: datetime.date | None = None


@define(frozen=True, slots=True)
class GetHouseResult:
    """Every House figure, precomputed — the UI renders, never derives.

    ``example_sections`` names the sections whose figures are still the
    fixed example payload; the page says so until real figures replace them.
    ``asset`` is the couple's home and its share settings, None before setup.
    """

    figures: HouseFigures
    example_sections: frozenset[str]
    asset: CoOwnedAsset | None


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


def _set_aside(
    pots: tuple[PotBalance, ...],
    funds: tuple[OwnerFunds, ...],
    asset: CoOwnedAsset | None,
) -> SetAsideSection:
    """One bucket for each pot, the unassigned pot last, and each owner's
    deposits. The bank balance the asset holds stands beside the total; the
    bank balance beside each pot stays unknown."""
    return set_aside_section(
        tuple(bucket(p.name, p.balance, is_unassigned=p.is_unassigned) for p in pots),
        owners=tuple(map(owner_deposits, funds)),
        bank_balance=asset.bank_balance if asset else None,
        bank_balance_as_of=asset.bank_balance_as_of if asset else None,
    )


@define(frozen=True, slots=True)
class _LoanSections:
    """The House sections of the loans and obligations, named as the
    response names them."""

    loans: tuple[LoanFigures, ...]
    past_loans: tuple[LoanFigures, ...]
    upcoming: tuple[ObligationFigures, ...]
    recent_paid: tuple[ObligationFigures, ...]


async def _loans_and_obligations(
    uow: UnitOfWorkProtocol,
    asset: CoOwnedAsset,
    rows: HouseRows,
    pots: tuple[PotBalance, ...],
    ctx: ReconciliationContext,
    as_of: datetime.date,
) -> _LoanSections:
    """The asset's loans, open and past, and its obligations: the unpaid
    ones in due order, each against what its pot has left, and the newest
    paid ones."""
    loans = await uow.loans.get_by_asset_id(asset.id)
    obligations = await uow.obligations.get_by_asset_id(asset.id)
    figures = loan_figures(loans, rows.loans, obligations, ctx.person_ids, as_of)
    due = [obligation_figures(o, as_of) for o in upcoming(obligations)]
    return _LoanSections(
        loans=tuple(f for f in figures if f.closed_on is None),
        past_loans=tuple(f for f in figures if f.closed_on is not None),
        upcoming=with_shortfalls(due, {p.name: p.balance for p in pots}),
        recent_paid=tuple(
            obligation_figures(o, as_of) for o in recently_paid(obligations)
        ),
    )


async def _real_sections(
    uow: UnitOfWorkProtocol,
    joint: list[Account],
    asset: CoOwnedAsset | None,
    ctx: ReconciliationContext,
    as_of: datetime.date,
) -> dict[str, object]:
    """The sections whose data exists, by field name, from the rows dated
    through `as_of`: Set aside and Recent activity once a joint account or
    the asset exists, and every other section once the asset does. Put in's
    unspent deposits are Set aside's."""
    rows = await fetch_house_rows(
        uow, [a.id for a in joint], as_of, with_asset=asset is not None
    )
    funds = compute_owner_funds(rows.joint, ctx.person_ids, ctx.non_spending_categories)
    pots = compute_pot_balances(rows.joint)
    real: dict[str, object] = {
        "set_aside": _set_aside(pots, funds, asset),
        "recent_activity": _recent_activity(rows.joint, ctx, joint),
    }
    if asset is not None:
        capital = capital_accounts(
            rows.shares, ctx.person_ids, asset, (as_of.year, as_of.month)
        )
        real["put_in"] = put_in_section(
            ctx.person_ids,
            capital.by_kind,
            unspent_deposits=tuple(OwnerAmount(f.person_id, f.unspent) for f in funds),
        )
        real["shares"] = shares_section(capital.history)
        sections = await _loans_and_obligations(uow, asset, rows, pots, ctx, as_of)
        real |= attrs.asdict(sections, recurse=False)
    return real


@define(slots=True)
class GetHouseUseCase:
    async def execute(
        self, command: GetHouseCommand, uow: UnitOfWorkProtocol
    ) -> GetHouseResult:
        """The House figures: real where their data exists, else the example.

        Once a joint account exists, the sections built from its rows are
        real; once the asset exists, every section is. Only real sections
        leave `example_sections`. The example sections then name the couple,
        so every owner list keys on the same persons, and every real figure
        counts the rows dated through `command.as_of`.
        """
        async with uow:
            joint = joint_accounts(await uow.accounts.get_all())
            asset = await uow.co_owned_assets.get_current()
            if not joint and asset is None:
                return GetHouseResult(
                    figures=EXAMPLE_HOUSE, example_sections=HOUSE_SECTIONS, asset=None
                )
            ctx = await load_reconciliation_context(uow)
            as_of = command.as_of or datetime.datetime.now(datetime.UTC).date()
            real = await _real_sections(uow, joint, asset, ctx, as_of)
            persons = tuple(HousePerson(p.id, p.name) for p in ctx.persons)
            first, second = (p.id for p in persons)
            figures = evolve(
                example_house(first, second), as_of=as_of, persons=persons, **real
            )
            return GetHouseResult(
                figures=figures,
                example_sections=HOUSE_SECTIONS.difference(real),
                asset=asset,
            )
