import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock,
  HandCoins,
  LayoutDashboard,
  Lock,
  PieChart,
  Upload,
} from "lucide-react";
import { useMemo } from "react";
import { Link, useNavigate } from "react-router";
import { useGetDashboard } from "@/api/generated/dashboard/dashboard";
import type {
  BudgetAlertResponse,
  DashboardResponse,
  MonthHistoryEntryResponse,
  PersonalMonthHistoryEntryResponse,
} from "@/api/generated/model";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { PageEmpty, PageError, PageLoading } from "@/components/PageStates";
import { PersonBadge } from "@/components/PersonBadge";
import { ProgressBar } from "@/components/ProgressBar";
import { SectionHeader } from "@/components/SectionHeader";
import { SegmentedControl } from "@/components/SegmentedControl";
import { StatsGrid } from "@/components/StatsGrid";
import { UnmappedCategoriesWarning } from "@/components/UnmappedCategoriesWarning";
import { UploadStatusRow } from "@/components/UploadStatusRow";
import { cn } from "@/lib/cn";
import {
  type DashboardScope,
  useDashboardFilters,
} from "@/lib/dashboard-filters";
import {
  buildSettlementLabel,
  currentYear,
  formatCurrency,
  formatMonthSpan,
  MONTHS,
  SHORT_MONTHS,
} from "@/lib/format";
import { getHealthStyle } from "@/lib/health-styles";
import { actionLinkClass } from "@/lib/input-styles";
import { heroCardClass, PAGE_PADDING, tableHeaderRowClass } from "@/lib/layout";
import { PERSON_SCOPE_OPTIONS } from "@/lib/person-scope";
import { usePersonMaps } from "@/lib/persons";

// --- Stats ---

function useTimeLabels(data: DashboardResponse) {
  const month = SHORT_MONTHS[data.current_month_month - 1] ?? "";
  const year = data.current_month_year;
  return {
    thisMonth: `${month} ${year}`,
    ytdRange: `Jan\u2013${month} ${year}`,
  };
}

function HouseholdStats({
  data,
  personNames,
}: {
  data: DashboardResponse;
  personNames: Map<string, string>;
}) {
  const { thisMonth, ytdRange } = useTimeLabels(data);
  const ytdLabel = buildSettlementLabel(data.ytd_net_settlement, personNames);
  return (
    <StatsGrid
      stats={[
        {
          label: "Household spending",
          value: formatCurrency(data.household_spending_month),
          description: `All expenses in the household budget, ${thisMonth}`,
        },
        {
          label: "Household YTD",
          value: formatCurrency(data.household_spending_ytd),
          description: `Cumulative household spending, ${ytdRange}`,
        },
        {
          label: "YTD balance",
          value: ytdLabel,
          description: `Net settlement, ${ytdRange}`,
        },
        {
          label: "Settled this year",
          value: formatCurrency(data.ytd_total_settled),
          description: "Payments recorded between you",
        },
      ]}
    />
  );
}

function PersonalStats({ data }: { data: DashboardResponse }) {
  const { thisMonth, ytdRange } = useTimeLabels(data);
  return (
    <StatsGrid
      stats={[
        {
          label: "My spending",
          value: formatCurrency(data.my_spending_month ?? 0),
          description: `My share of household + my personal, ${thisMonth}`,
        },
        {
          label: "Household share",
          value: formatCurrency(data.my_household_share_month ?? 0),
          description: "My portion of household expenses",
        },
        {
          label: "Personal only",
          value: formatCurrency(data.my_personal_spending_month ?? 0),
          description: "Personal spending I paid",
        },
        {
          label: "My spending YTD",
          value: formatCurrency(data.my_spending_ytd ?? 0),
          description: `All my spending, ${ytdRange}`,
        },
      ]}
    />
  );
}

function AllStats({
  data,
  personNames,
}: {
  data: DashboardResponse;
  personNames: Map<string, string>;
}) {
  const { thisMonth, ytdRange } = useTimeLabels(data);
  const ytdLabel = buildSettlementLabel(data.ytd_net_settlement, personNames);
  return (
    <StatsGrid
      stats={[
        {
          label: "Total spending",
          value: formatCurrency(data.total_all_spending_month ?? 0),
          description: `Household + all personal from both people, ${thisMonth}`,
        },
        {
          label: "Household portion",
          value: formatCurrency(data.household_spending_month),
          description: "All expenses in the household budget",
        },
        {
          label: "YTD balance",
          value: ytdLabel,
          description: `Net settlement, ${ytdRange}`,
        },
        {
          label: "Total spending YTD",
          value: formatCurrency(data.total_all_spending_ytd ?? 0),
          description: `All spending from both people, ${ytdRange}`,
        },
      ]}
    />
  );
}

// --- Quick Actions ---

function QuickActions({ scope }: { scope: DashboardScope }) {
  const scopeParam = scope === "personal" ? "?scope=personal" : "";
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:gap-3">
      <Link to="/upload" className={actionLinkClass}>
        <Upload className="size-4" />
        Upload CSV
      </Link>
      {scope === "personal" ? (
        <Link to={`/budget${scopeParam}`} className={actionLinkClass}>
          <PieChart className="size-4" />
          View Budget
        </Link>
      ) : (
        <Link to="/settle" className={actionLinkClass}>
          <HandCoins className="size-4" />
          Settle Up
        </Link>
      )}
      <Link to={`/transactions${scopeParam}`} className={actionLinkClass}>
        View Transactions
        <ArrowRight className="size-4" />
      </Link>
    </div>
  );
}

// --- Budget Alerts (personal scope only) ---

function BudgetAlerts({ alerts }: { alerts: BudgetAlertResponse[] }) {
  if (alerts.length === 0) return null;
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-medium text-foreground">Budget alerts</h2>
        <Link
          to="/budget?scope=personal"
          className="text-xs font-medium text-primary hover:underline"
        >
          View Budget
        </Link>
      </div>
      <div className="space-y-3">
        {alerts.map((alert) => {
          const pct =
            alert.monthly_budget > 0
              ? Math.min(
                  (alert.monthly_spent / alert.monthly_budget) * 100,
                  150,
                )
              : 100;
          const style = getHealthStyle(alert.health);
          const Icon = alert.health === "over_budget" ? AlertCircle : Clock;
          return (
            <div key={alert.group_id}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="flex items-center gap-1.5 font-medium text-foreground">
                  <Icon className={`size-3.5 ${style.color}`} />
                  {alert.group_name}
                </span>
                <span className={`tabular-nums ${style.color}`}>
                  {formatCurrency(alert.monthly_spent)} /{" "}
                  {formatCurrency(alert.monthly_budget)}
                </span>
              </div>
              <ProgressBar pct={Math.min(pct, 100)} barColor={style.barColor} />
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// --- Settlement Hero ---

function SettlementHero({
  data,
  getPersonName,
  getPersonColor,
}: {
  data: DashboardResponse;
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
}) {
  // The requested year's balance, precomputed server-side — the same row
  // the Settle Up hero renders for that year.
  const yearRow = data.settlement_year;
  const settlement = yearRow.balance;
  const year = yearRow.year;

  if (!settlement) {
    return (
      <div className={cn(heroCardClass, "p-4 sm:p-6")}>
        <p className="mb-1 text-center text-xs font-medium tracking-wider text-muted-foreground uppercase">
          Settlement
        </p>
        <p className="text-center text-base font-semibold text-primary sm:text-lg">
          <span className="inline-flex items-center gap-2">
            <CheckCircle2 className="size-5" />
            {yearRow.charged
              ? `${year} is settled`
              : `Nothing to settle in ${year}`}
          </span>
        </p>
      </div>
    );
  }

  const personId = data.current_person_id;
  const isPersonalPerspective = data.scope === "personal" && personId;
  const iOwe = isPersonalPerspective && settlement.from_person_id === personId;
  const iAmOwed = isPersonalPerspective && settlement.to_person_id === personId;

  return (
    <Link
      to="/settle"
      className={cn(
        heroCardClass,
        "block p-4 transition-colors hover:bg-muted/50 sm:p-6",
      )}
    >
      <p className="mb-1 text-center text-xs font-medium tracking-wider text-muted-foreground uppercase">
        Balance for {year}
      </p>
      <p className="text-center text-base font-semibold text-foreground sm:text-lg">
        {iOwe ? (
          <>
            You owe {getPersonName(settlement.to_person_id ?? "")}{" "}
            <span className="tabular-nums">
              {formatCurrency(settlement.amount)}
            </span>
          </>
        ) : iAmOwed ? (
          <>
            {getPersonName(settlement.from_person_id)} owes you{" "}
            <span className="tabular-nums">
              {formatCurrency(settlement.amount)}
            </span>
          </>
        ) : (
          <>
            <PersonBadge
              name={getPersonName(settlement.from_person_id)}
              accentColor={getPersonColor(settlement.from_person_id)}
              size="base"
            />{" "}
            owes {getPersonName(settlement.to_person_id ?? "")}{" "}
            <span className="tabular-nums">
              {formatCurrency(settlement.amount)}
            </span>
          </>
        )}
      </p>
      {yearRow.span && (
        <p className="mt-1 text-center text-xs text-muted-foreground">
          covers {formatMonthSpan(yearRow.span)}
        </p>
      )}
      {/* The working line — the headline is never a bare number the couple
          has to take on trust. */}
      {yearRow.paid && (
        <p className="mt-1 text-center text-xs text-muted-foreground tabular-nums">
          {formatCurrency(yearRow.charged?.amount ?? 0)} charged,{" "}
          {formatCurrency(yearRow.paid.amount)} paid in {year}
        </p>
      )}
      <p className="mt-1 text-center text-sm text-primary">
        Settle Up <ArrowRight className="ml-1 inline size-3.5" />
      </p>
    </Link>
  );
}

// --- Month History ---

function HouseholdMonthHistory({
  entries,
  personNames,
  spendingKey,
}: {
  entries: MonthHistoryEntryResponse[];
  personNames: Map<string, string>;
  spendingKey: "total_household_spending" | "total_all_spending";
}) {
  const navigate = useNavigate();
  if (entries.length === 0) return null;

  const spendingLabel =
    spendingKey === "total_all_spending" ? "Total Spending" : "Spending";

  return (
    <Card>
      <SectionHeader
        title="Month History"
        description="Track spending and settlement status across months"
      />
      <table className="w-full text-sm">
        <thead>
          <tr className={tableHeaderRowClass}>
            <th className="pb-2 pr-4 font-medium">Month</th>
            <th className="pb-2 pr-4 font-medium">Settlement</th>
            <th className="hidden pb-2 text-right font-medium sm:table-cell">
              {spendingLabel}
            </th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const monthName = MONTHS[entry.month - 1] ?? "";
            // settlement_amount is the month's pre-payment gross; show the
            // still-unpaid balance (settlement_remaining) so a partially
            // settled row doesn't overstate what's owed.
            const status = entry.settlement_status;
            const label =
              status === "settled"
                ? "All settled"
                : buildSettlementLabel(
                    entry.settlement_from_person_id
                      ? {
                          amount: entry.settlement_remaining,
                          from_person_id: entry.settlement_from_person_id,
                          to_person_id:
                            entry.settlement_to_person_id ?? undefined,
                        }
                      : null,
                    personNames,
                    { settledLabel: "All settled", includeToName: true },
                  );
            const spending =
              spendingKey === "total_all_spending" &&
              entry.total_all_spending != null
                ? entry.total_all_spending
                : entry.total_household_spending;

            return (
              <tr
                key={`${entry.year}-${entry.month}`}
                className="cursor-pointer border-b border-border-muted transition-colors duration-150 hover:bg-muted/50"
                onClick={() =>
                  navigate(
                    `/transactions?year=${entry.year}&month=${entry.month}`,
                  )
                }
              >
                <td className="py-2.5 pr-4 font-medium text-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    {monthName} {entry.year}
                    {entry.is_finalized && (
                      <Lock className="size-3 text-primary-muted-foreground" />
                    )}
                  </span>
                </td>
                <td className="py-2.5 pr-4 text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    {status === "settled" ? (
                      <CheckCircle2 className="size-3 text-positive" />
                    ) : status === "partially_settled" ? (
                      <Clock className="size-3 text-warning-muted-foreground" />
                    ) : (
                      <ArrowRight className="size-3 text-muted-foreground/70" />
                    )}
                    {label}
                    {status === "partially_settled" && (
                      <span className="text-xs text-warning-muted-foreground">
                        · partial
                      </span>
                    )}
                    {status === "carried_forward" && (
                      <span className="text-xs text-muted-foreground/70">
                        · carried forward
                      </span>
                    )}
                  </span>
                </td>
                <td className="hidden py-2.5 text-right tabular-nums text-foreground sm:table-cell">
                  {formatCurrency(spending)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}

function PersonalMonthHistory({
  entries,
  year,
}: {
  entries: PersonalMonthHistoryEntryResponse[];
  year: number;
}) {
  const navigate = useNavigate();
  if (entries.length === 0) return null;

  return (
    <Card>
      <SectionHeader
        title="Month History"
        description="Your spending across months"
      />
      <table className="w-full text-sm">
        <thead>
          <tr className={tableHeaderRowClass}>
            <th className="pb-2 pr-4 font-medium">Month</th>
            <th className="pb-2 pr-4 text-right font-medium">My Spending</th>
            <th className="hidden pb-2 text-right font-medium sm:table-cell">
              Breakdown
            </th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const monthName = MONTHS[entry.month - 1] ?? "";
            return (
              <tr
                key={`${entry.year}-${entry.month}`}
                className="cursor-pointer border-b border-border-muted transition-colors duration-150 hover:bg-muted/50"
                onClick={() =>
                  navigate(
                    `/transactions?year=${year}&month=${entry.month}&scope=personal`,
                  )
                }
              >
                <td className="py-2.5 pr-4 font-medium text-foreground">
                  {monthName} {entry.year}
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums text-foreground">
                  {formatCurrency(entry.total_spending)}
                </td>
                <td className="hidden py-2.5 text-right text-muted-foreground sm:table-cell">
                  <span className="tabular-nums">
                    {formatCurrency(entry.household_portion)} household
                  </span>
                  {entry.own_spending > 0 && (
                    <span className="tabular-nums">
                      {" / "}
                      {formatCurrency(entry.own_spending)} personal
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}

// --- Page ---

const SCOPE_OPTIONS: Array<{ value: DashboardScope; label: string }> = [
  ...PERSON_SCOPE_OPTIONS,
  { value: "all", label: "All" },
];

export function DashboardPage() {
  const { scope, setScope } = useDashboardFilters();
  // Always send the browser's local year — the dashboard has no date
  // picker, so it defaults to "now," and a UTC default would show an
  // empty next-year dashboard for the entire evening of Dec 31.
  const params = useMemo(
    () =>
      scope === "household"
        ? { year: currentYear() }
        : { year: currentYear(), scope },
    [scope],
  );

  const {
    data: response,
    isLoading,
    error,
    refetch,
  } = useGetDashboard(params, { query: { refetchInterval: 5_000 } });
  const data = response?.status === 200 ? response.data : undefined;

  const { personNames, getPersonName, getPersonColor } = usePersonMaps(
    data?.persons,
  );

  const monthLabel = data
    ? `${MONTHS[data.current_month_month - 1] ?? ""} ${data.current_month_year}`
    : "";
  const isEmpty =
    data &&
    data.current_month_transaction_count === 0 &&
    data.month_history.length === 0 &&
    !(data.personal_month_history && data.personal_month_history.length > 0);

  const emptyMessage =
    scope === "personal"
      ? "Upload a CSV to see your spending."
      : scope === "all"
        ? "Upload a CSV to get started."
        : "Upload a CSV to see your household spending.";

  return (
    <div className={`mx-auto max-w-5xl ${PAGE_PADDING}`}>
      <PageHeader
        icon={<LayoutDashboard className="size-6" />}
        title="Dashboard"
        badge={
          data?.is_finalized ? (
            <span
              className="inline-flex items-center gap-1 rounded-md bg-primary-muted px-2 py-0.5 text-xs font-medium text-primary-muted-foreground"
              title="Month locked"
            >
              <Lock className="size-3" />
              Locked
            </span>
          ) : undefined
        }
      />

      <div className="mb-6">
        <SegmentedControl<DashboardScope>
          options={SCOPE_OPTIONS}
          value={scope}
          onChange={setScope}
          size="sm"
        />
      </div>

      {isLoading && <PageLoading label="Loading dashboard..." />}

      {error && <PageError error={error} onRetry={() => refetch()} />}

      {isEmpty && (
        <PageEmpty
          icon={<Upload />}
          heading={`No data for ${monthLabel}`}
          description={emptyMessage}
          action={
            <Link
              to="/upload"
              className="text-sm font-medium text-primary hover:underline"
            >
              Upload CSV
            </Link>
          }
        />
      )}

      {data && !isEmpty && (
        <div className="space-y-6">
          <SettlementHero
            data={data}
            getPersonName={getPersonName}
            getPersonColor={getPersonColor}
          />

          <UploadStatusRow
            statuses={data.upload_statuses}
            getPersonColor={getPersonColor}
          />

          {scope === "household" && (
            <HouseholdStats data={data} personNames={personNames} />
          )}
          {scope === "personal" && <PersonalStats data={data} />}
          {scope === "all" && (
            <AllStats data={data} personNames={personNames} />
          )}

          <QuickActions scope={scope} />

          {scope === "personal" &&
            data.budget_alerts &&
            data.budget_alerts.length > 0 && (
              <BudgetAlerts alerts={data.budget_alerts} />
            )}

          {scope === "personal" && data.personal_month_history ? (
            <PersonalMonthHistory
              entries={data.personal_month_history}
              year={data.current_month_year}
            />
          ) : (
            <HouseholdMonthHistory
              entries={data.month_history}
              personNames={personNames}
              spendingKey={
                scope === "all"
                  ? "total_all_spending"
                  : "total_household_spending"
              }
            />
          )}

          {scope !== "personal" && (
            <UnmappedCategoriesWarning categories={data.unmapped_categories} />
          )}
        </div>
      )}
    </div>
  );
}
