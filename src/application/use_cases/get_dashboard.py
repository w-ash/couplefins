from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    Scope,
    optional_month_range,
    positive_int,
)
from src.application.use_cases._shared.date_math import month_bounds, partition_by_month
from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.application.use_cases._shared.transactions import find_all_unmapped_categories
from src.application.use_cases._shared.upload_status import (
    UploadStatus,
    build_upload_statuses,
)
from src.domain.budget import (
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
from src.domain.reconciliation import (
    ReconciliationSummary,
    SettlementResult,
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
    settlement_amount: Decimal
    settlement_from_person_id: UUID | None
    settlement_to_person_id: UUID | None
    is_finalized: bool
    is_settled: bool
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
    upload_statuses: list[UploadStatus]
    household_spending_month: Decimal
    household_spending_ytd: Decimal
    ytd_settlement: SettlementResult | None
    ytd_total_settled: Decimal
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


def _build_month_history(
    summaries: dict[int, ReconciliationSummary],
    year: int,
    finalized_months: set[int],
    settlements_by_month: dict[int, list[Settlement]],
    all_spending_by_month: dict[int, Decimal] | None = None,
) -> list[MonthHistoryEntry]:
    entries: list[MonthHistoryEntry] = []
    for month in sorted(summaries, reverse=True):
        settlement = summaries[month].settlement
        owed = settlement.amount if settlement else Decimal(0)
        month_settlements = settlements_by_month.get(month, [])
        total_settled = sum((s.amount for s in month_settlements), Decimal(0))
        is_settled = total_settled >= owed
        settled_at = (
            max(s.settled_at for s in month_settlements)
            if is_settled and month_settlements
            else None
        )
        entries.append(
            MonthHistoryEntry(
                year=year,
                month=month,
                total_household_spending=summaries[month].total_household_spending,
                settlement_amount=owed,
                settlement_from_person_id=settlement.from_person_id
                if settlement
                else None,
                settlement_to_person_id=settlement.to_person_id if settlement else None,
                is_finalized=month in finalized_months,
                is_settled=is_settled,
                settled_at=settled_at,
                total_all_spending=(
                    all_spending_by_month[month]
                    if all_spending_by_month and month in all_spending_by_month
                    else None
                ),
            )
        )
    return entries


def _resolve_active_month(
    by_month: dict[int, list[Transaction]],
    finalized_months: set[int],
    fallback_month: int,
) -> int:
    """Pick the most relevant month for the dashboard.

    Fallback chain: latest unfinalized month with transactions →
    latest month with transactions → current calendar month.
    """
    if not by_month:
        return fallback_month
    unfinalized = sorted(
        (m for m in by_month if m not in finalized_months), reverse=True
    )
    if unfinalized:
        return unfinalized[0]
    return max(by_month)


def _compute_personal_spending(
    txs: list[Transaction], person_id: UUID
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute (total, household_portion, own_spending) for one person."""
    household_portion = Decimal(0)
    own_spending = Decimal(0)
    for tx in txs:
        if tx.is_excluded or tx.is_settlement:
            continue
        if tx.household:
            household_portion += compute_person_share(tx, person_id)
        elif tx.payer_person_id == person_id and tx.amount < 0:
            own_spending += abs(tx.amount)
    return household_portion + own_spending, household_portion, own_spending


def _compute_all_spending(txs: list[Transaction]) -> Decimal:
    """Total absolute spending across all transaction types."""
    total = Decimal(0)
    for tx in txs:
        if tx.is_excluded or tx.is_settlement:
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
        month_budgets,
        year_budgets,
        year_txs,
        category_lookup,
        category_groups,
        year,
        month,
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
        if status.monthly_health in alert_statuses and status.monthly_budget is not None
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

            year_periods = await uow.reconciliation_periods.get_by_year(command.year)
            finalized_months = {p.month for p in year_periods if p.is_finalized}
            all_year_settlements = await uow.settlements.get_by_year(command.year)

            now = datetime.now(tz=UTC)
            active_month = (
                command.month
                if command.month is not None
                else _resolve_active_month(
                    by_month_household, finalized_months, now.month
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

            ytd_household_txs = [
                tx for tx in household_txs if tx.date.month <= active_month
            ]
            ytd_summary = reconcile(
                ytd_household_txs,
                ctx.persons,
                ctx.categories,
                ctx.category_groups,
                start_date=date(command.year, 1, 1),
                end_date=end,
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
                upload_statuses=upload_statuses,
                household_spending_month=household_spending_month,
                household_spending_ytd=household_spending_ytd,
                ytd_settlement=ytd_summary.settlement,
                ytd_total_settled=sum(
                    (s.amount for s in all_year_settlements if s.month <= active_month),
                    Decimal(0),
                ),
                month_history=_build_month_history(
                    month_summaries,
                    command.year,
                    finalized_months,
                    partition_by_month(all_year_settlements, lambda s: s.month),
                    all_spending_by_month=(
                        all_data.spending_by_month if all_data else None
                    ),
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
