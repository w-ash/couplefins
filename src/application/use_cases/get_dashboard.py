from collections.abc import Collection
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from attrs import define, evolve, field

from src.application.use_cases._shared.command_validators import (
    Scope,
    optional_month_range,
    positive_int,
)
from src.application.use_cases._shared.date_math import month_bounds, partition_by_month
from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.application.use_cases._shared.settlement_math import load_settlement_ledger
from src.application.use_cases._shared.transactions import find_all_unmapped_categories
from src.application.use_cases._shared.upload_status import (
    UploadStatus,
    build_upload_statuses,
)
from src.domain.budget import (
    BudgetOverviewInputs,
    HealthStatus,
    compute_person_share,
    compute_personal_budget_overview,
)
from src.domain.categories import build_category_lookup
from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.entities.person import Person
from src.domain.entities.settlement import Settlement
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import ValidationError
from src.domain.filters import is_reconciliation_relevant
from src.domain.ledger import (
    LedgerMonth,
    MonthKey,
    MonthSettlementStatus,
    month_remaining_result,
    sum_settlement_results,
)
from src.domain.reconciliation import (
    ReconciliationSummary,
    SettlementResult,
    compute_gross_settlement,
    reconcile,
    reconcile_all_months,
)
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetDashboardCommand:
    year: int = field(validator=positive_int)
    month: int | None = field(default=None, validator=optional_month_range)
    scope: Scope = "household"
    person_id: UUID | None = None

    def __attrs_post_init__(self) -> None:
        if self.scope == "personal" and self.person_id is None:
            raise ValidationError("person_id is required for personal scope")


@define(frozen=True, slots=True)
class MonthHistoryEntry:
    year: int
    month: int
    total_household_spending: Decimal
    # The month's gross settlement position (direction omitted when zero).
    settlement_amount: Decimal
    settlement_from_person_id: UUID | None
    settlement_to_person_id: UUID | None
    is_finalized: bool
    is_settled: bool
    # Ledger-derived: settled | partially_settled | carried_forward
    settlement_status: str
    settled_at: datetime | None
    total_all_spending: Decimal | None = None


@define(frozen=True, slots=True)
class PersonalMonthHistoryEntry:
    year: int
    month: int
    total_spending: Decimal
    household_portion: Decimal
    own_spending: Decimal


@define(frozen=True, slots=True)
class BudgetAlert:
    group_id: UUID
    group_name: str
    monthly_budget: Decimal
    monthly_spent: Decimal
    health: HealthStatus


@define(frozen=True, slots=True)
class GetDashboardResult:
    scope: Scope
    current_person_id: UUID | None
    current_month: ReconciliationSummary
    current_month_net_settlement: SettlementResult | None
    upload_statuses: list[UploadStatus]
    household_spending_month: Decimal
    household_spending_ytd: Decimal
    ytd_settlement: SettlementResult | None
    ytd_net_settlement: SettlementResult | None
    ytd_total_settled: Decimal
    outstanding_balance: SettlementResult | None
    outstanding_span: tuple[MonthKey, MonthKey] | None
    month_history: list[MonthHistoryEntry]
    persons: list[Person]
    unmapped_categories: list[str]
    is_finalized: bool
    finalized_at: datetime | None
    # Personal scope
    my_spending_month: Decimal | None = None
    my_household_share_month: Decimal | None = None
    my_personal_spending_month: Decimal | None = None
    my_spending_ytd: Decimal | None = None
    personal_month_history: list[PersonalMonthHistoryEntry] | None = None
    budget_alerts: list[BudgetAlert] | None = None
    # All scope
    total_all_spending_month: Decimal | None = None
    total_all_spending_ytd: Decimal | None = None


@define(frozen=True, slots=True)
class _MonthHistoryInputs:
    """Bundled inputs to `_build_month_history` — keeps the function's
    signature at one parameter regardless of how many sources feed it."""

    summaries: dict[int, ReconciliationSummary]
    year: int
    finalized_months: set[int]
    ledger_rows: dict[int, LedgerMonth]
    settlements_by_id: dict[UUID, Settlement]
    by_month_household: dict[int, list[Transaction]]
    all_spending_by_month: dict[int, Decimal] | None = None


def _month_settled_at(
    row: LedgerMonth, settlements_by_id: dict[UUID, Settlement]
) -> datetime | None:
    """When the month's covering payments landed — the newest one wins."""
    return max(
        (
            settlements_by_id[sid].settled_at
            for sid in row.covering_settlement_ids
            if sid in settlements_by_id
        ),
        default=None,
    )


def _build_month_history(inputs: _MonthHistoryInputs) -> list[MonthHistoryEntry]:
    entries: list[MonthHistoryEntry] = []
    # Union: a month can have settlement-relevant rows (e.g. spotted) without
    # any household spending, and vice versa.
    for month in sorted(set(inputs.summaries) | set(inputs.ledger_rows), reverse=True):
        row = inputs.ledger_rows.get(month)
        # Display direction only for a real debt — a zero-amount gross
        # carries an arbitrary direction.
        gross = row.gross if row and row.gross and row.gross.amount > 0 else None
        # No ledger row → no settlement-relevant activity → trivially settled.
        status = row.status if row else MonthSettlementStatus.SETTLED
        entries.append(
            MonthHistoryEntry(
                year=inputs.year,
                month=month,
                # True household metric (all household=true, including
                # no-split rows) — the same figure the now-card uses, not
                # reconcile()'s split-only total_household_spending.
                total_household_spending=_compute_all_spending(
                    inputs.by_month_household.get(month, [])
                ),
                settlement_amount=gross.amount if gross else Decimal(0),
                settlement_from_person_id=gross.from_person_id if gross else None,
                settlement_to_person_id=gross.to_person_id if gross else None,
                is_finalized=month in inputs.finalized_months,
                is_settled=status is MonthSettlementStatus.SETTLED,
                settlement_status=status,
                settled_at=(
                    _month_settled_at(row, inputs.settlements_by_id) if row else None
                ),
                total_all_spending=(
                    inputs.all_spending_by_month[month]
                    if inputs.all_spending_by_month
                    and month in inputs.all_spending_by_month
                    else None
                ),
            )
        )
    return entries


def _resolve_active_month(
    months_with_data: Collection[int],
    finalized_months: set[int],
    fallback_month: int,
) -> int:
    """Pick the most relevant month for the dashboard.

    Fallback chain: latest unfinalized month with transactions →
    latest month with transactions → current calendar month.
    """
    if not months_with_data:
        return fallback_month
    unfinalized = sorted(
        (m for m in months_with_data if m not in finalized_months), reverse=True
    )
    if unfinalized:
        return unfinalized[0]
    return max(months_with_data)


def _compute_personal_spending(
    txs: list[Transaction], person_id: UUID
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute (total, household_portion, own_spending) for one person.

    Personal spending is this person's *share* of non-household rows — the
    payer's percentage when they paid, or 100 - payer_percentage when their
    partner fronted it and they owe some or all of it back (e.g. spotted).
    """
    household_portion = Decimal(0)
    own_spending = Decimal(0)
    for tx in txs:
        if not is_reconciliation_relevant(tx):
            continue
        # Sign-aware in both branches: a refund subtracts the share instead
        # of inflating it.
        share = compute_person_share(tx, person_id)
        if tx.household:
            household_portion += share if tx.amount < 0 else -share
        else:
            own_spending += share if tx.amount < 0 else -share
    return household_portion + own_spending, household_portion, own_spending


def _compute_all_spending(txs: list[Transaction]) -> Decimal:
    """Total absolute spending across all transaction types."""
    total = Decimal(0)
    for tx in txs:
        if not is_reconciliation_relevant(tx):
            continue
        if tx.amount < 0:
            total += abs(tx.amount)
    return total


def _build_budget_alerts(  # noqa: PLR0913, PLR0917
    month_budgets: list[CategoryGroupBudget],
    year_budgets: list[CategoryGroupBudget],
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    category_groups: list[CategoryGroup],
    year: int,
    month: int,
    person_id: UUID,
) -> list[BudgetAlert]:
    """Compute personal budget overview and extract top alerts."""
    overview = compute_personal_budget_overview(
        BudgetOverviewInputs(
            month_budgets,
            year_budgets,
            year_txs,
            category_lookup,
            category_groups,
            year,
            month,
        ),
        person_id,
    )
    alert_statuses: set[HealthStatus] = {"near_limit", "over_budget"}
    alerts = [
        BudgetAlert(
            group_id=status.group_id,
            group_name=status.group_name,
            monthly_budget=status.monthly_budget,
            monthly_spent=status.monthly_spent,
            health=status.monthly_health,
        )
        for status in overview.group_statuses
        if status.group_id is not None
        and status.monthly_health in alert_statuses
        and status.monthly_budget is not None
    ]
    # Sort: over_budget first, then by overage
    alerts.sort(
        key=lambda a: (
            0 if a.health == "over_budget" else 1,
            -(a.monthly_spent - a.monthly_budget),
        )
    )
    return alerts[:5]


@define(frozen=True, slots=True)
class _AllScopeData:
    spending_by_month: dict[int, Decimal]
    month_spending: Decimal
    ytd_spending: Decimal


@define(frozen=True, slots=True)
class _PersonalScopeData:
    spending_month: Decimal
    household_share_month: Decimal
    personal_spending_month: Decimal
    spending_ytd: Decimal
    month_history: list[PersonalMonthHistoryEntry]
    budget_alerts: list[BudgetAlert]


def _compute_all_scope_data(
    all_year_txs: list[Transaction], active_month: int
) -> _AllScopeData:
    by_month_all = partition_by_month(all_year_txs, lambda tx: tx.date.month)
    spending_by_month = {
        m: _compute_all_spending(txs) for m, txs in by_month_all.items()
    }
    ytd_spending = sum(
        (v for m, v in spending_by_month.items() if m <= active_month),
        Decimal(0),
    )
    return _AllScopeData(
        spending_by_month=spending_by_month,
        month_spending=spending_by_month.get(active_month, Decimal(0)),
        ytd_spending=ytd_spending,
    )


def _compute_personal_scope_data(  # noqa: PLR0913, PLR0917
    all_year_txs: list[Transaction],
    person_id: UUID,
    active_month: int,
    year: int,
    month_budgets: list[CategoryGroupBudget],
    year_budgets: list[CategoryGroupBudget],
    category_lookup: dict[str, tuple[UUID, str]],
    category_groups: list[CategoryGroup],
) -> _PersonalScopeData:
    # Compute once per month, derive active-month and YTD from the results
    by_month = partition_by_month(all_year_txs, lambda tx: tx.date.month)
    month_results = {
        m: _compute_personal_spending(by_month[m], person_id) for m in by_month
    }

    spending_month, household_share, personal_own = month_results.get(
        active_month, (Decimal(0), Decimal(0), Decimal(0))
    )
    spending_ytd = sum(
        (total for m, (total, _, _) in month_results.items() if m <= active_month),
        Decimal(0),
    )

    history = [
        PersonalMonthHistoryEntry(
            year=year,
            month=m,
            total_spending=total,
            household_portion=household_portion,
            own_spending=own,
        )
        for m in sorted(month_results, reverse=True)
        for total, household_portion, own in [month_results[m]]
    ]

    alerts = _build_budget_alerts(
        month_budgets,
        year_budgets,
        all_year_txs,
        category_lookup,
        category_groups,
        year,
        active_month,
        person_id,
    )

    return _PersonalScopeData(
        spending_month=spending_month,
        household_share_month=household_share,
        personal_spending_month=personal_own,
        spending_ytd=spending_ytd,
        month_history=history,
        budget_alerts=alerts,
    )


@define(slots=True)
class GetDashboardUseCase:
    async def execute(  # noqa: PLR0914
        self, command: GetDashboardCommand, uow: UnitOfWorkProtocol
    ) -> GetDashboardResult:
        async with uow:
            ctx = await load_reconciliation_context(uow)

            # Fetch transactions: household-only for household scope, all otherwise
            if command.scope == "household":
                all_year_txs = await uow.transactions.get_household_by_year(
                    command.year
                )
                household_txs = all_year_txs
            else:
                all_year_txs = await uow.transactions.get_by_year(command.year)
                household_txs = [tx for tx in all_year_txs if tx.household]

            by_month_household = partition_by_month(
                household_txs, lambda tx: tx.date.month
            )

            # Settlement math runs on the all-time ledger over
            # payer_percentage < 100 rows regardless of the household flag —
            # a different universe than the spending aggregations above.
            bundle = await load_settlement_ledger(uow, ctx)
            ledger = bundle.ledger
            year_rows = {m.month: m for m in ledger.months if m.year == command.year}

            year_periods = await uow.reconciliation_periods.get_by_year(command.year)
            finalized_months = {p.month for p in year_periods if p.is_finalized}

            now = datetime.now(tz=UTC)
            active_month = (
                command.month
                if command.month is not None
                else _resolve_active_month(
                    set(year_rows) | set(by_month_household),
                    finalized_months,
                    now.month,
                )
            )

            # Reconcile household months (shared across all scopes)
            month_summaries = reconcile_all_months(
                by_month_household,
                ctx.persons,
                ctx.categories,
                ctx.category_groups,
                command.year,
            )
            start, end = month_bounds(command.year, active_month)
            current_month = month_summaries.get(
                active_month,
                reconcile(
                    [],
                    ctx.persons,
                    ctx.categories,
                    ctx.category_groups,
                    start_date=start,
                    end_date=end,
                ),
            )
            # The summary's spending figures describe household rows; its
            # settlement figure must cover all settlement-relevant rows.
            active_row = year_rows.get(active_month)
            current_month = evolve(
                current_month,
                settlement=(
                    active_row.gross
                    if active_row is not None
                    else compute_gross_settlement([], ctx.person_ids)
                ),
            )

            ytd_household_txs = [
                tx for tx in household_txs if tx.date.month <= active_month
            ]
            ytd_rows = [
                row for month, row in year_rows.items() if month <= active_month
            ]
            ytd_gross_settlement = sum_settlement_results(
                (row.gross for row in ytd_rows), ctx.person_ids
            )

            # True household spending (all household=true, including no-split)
            household_spending_month = _compute_all_spending(
                by_month_household.get(active_month, [])
            )
            household_spending_ytd = _compute_all_spending(ytd_household_txs)

            uploads = await uow.uploads.get_by_person_ids_with_transactions_in_period(
                ctx.person_ids, command.year, active_month
            )
            upload_statuses = build_upload_statuses(ctx.persons, uploads)

            current_period = next(
                (p for p in year_periods if p.month == active_month), None
            )

            # Scope-specific data
            all_data: _AllScopeData | None = None
            personal_data: _PersonalScopeData | None = None

            if command.scope == "all":
                all_data = _compute_all_scope_data(all_year_txs, active_month)

            if command.scope == "personal" and command.person_id is not None:
                category_lookup = build_category_lookup(
                    ctx.categories, ctx.category_groups
                )
                personal_year_budgets = await uow.category_group_budgets.get_by_year(
                    command.year, command.person_id
                )
                personal_month_budgets = [
                    b for b in personal_year_budgets if b.month == active_month
                ]
                personal_data = _compute_personal_scope_data(
                    all_year_txs,
                    command.person_id,
                    active_month,
                    command.year,
                    personal_month_budgets,
                    personal_year_budgets,
                    category_lookup,
                    ctx.category_groups,
                )
                upload_statuses = [
                    us for us in upload_statuses if us.person_id == command.person_id
                ]

            return GetDashboardResult(
                scope=command.scope,
                current_person_id=command.person_id,
                current_month=current_month,
                # The active month's ledger position: its gross minus what
                # FIFO applied to it — None when settled or absent.
                current_month_net_settlement=(
                    month_remaining_result(active_row)
                    if active_row is not None
                    else None
                ),
                upload_statuses=upload_statuses,
                household_spending_month=household_spending_month,
                household_spending_ytd=household_spending_ytd,
                ytd_settlement=ytd_gross_settlement,
                # What's still unpaid across the year's months through the
                # active month (payments already netted by the ledger).
                ytd_net_settlement=sum_settlement_results(
                    (month_remaining_result(row) for row in ytd_rows),
                    ctx.person_ids,
                ),
                # Annotation-independent: everything paid during this year.
                ytd_total_settled=sum(
                    (
                        s.amount
                        for s in bundle.settlements
                        if s.settled_at.year == command.year
                    ),
                    Decimal(0),
                ),
                outstanding_balance=ledger.outstanding,
                outstanding_span=ledger.span,
                month_history=_build_month_history(
                    _MonthHistoryInputs(
                        summaries=month_summaries,
                        year=command.year,
                        finalized_months=finalized_months,
                        ledger_rows=year_rows,
                        settlements_by_id={s.id: s for s in bundle.settlements},
                        by_month_household=by_month_household,
                        all_spending_by_month=(
                            all_data.spending_by_month if all_data else None
                        ),
                    )
                ),
                persons=ctx.persons,
                unmapped_categories=find_all_unmapped_categories(
                    ctx.categories,
                    {tx.category for tx in by_month_household.get(active_month, [])},
                ),
                is_finalized=current_period.is_finalized if current_period else False,
                finalized_at=current_period.finalized_at if current_period else None,
                my_spending_month=(
                    personal_data.spending_month if personal_data else None
                ),
                my_household_share_month=(
                    personal_data.household_share_month if personal_data else None
                ),
                my_personal_spending_month=(
                    personal_data.personal_spending_month if personal_data else None
                ),
                my_spending_ytd=(personal_data.spending_ytd if personal_data else None),
                personal_month_history=(
                    personal_data.month_history if personal_data else None
                ),
                budget_alerts=(personal_data.budget_alerts if personal_data else None),
                total_all_spending_month=(
                    all_data.month_spending if all_data else None
                ),
                total_all_spending_ytd=(all_data.ytd_spending if all_data else None),
            )
