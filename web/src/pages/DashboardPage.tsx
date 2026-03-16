import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  HandCoins,
  LayoutDashboard,
  Lock,
  Upload,
} from "lucide-react";
import { Link, useNavigate } from "react-router";
import { PageHeader } from "@/components/PageHeader";
import { PageEmpty, PageError, PageLoading } from "@/components/PageStates";
import { StatsGrid } from "@/components/StatsGrid";
import { UnmappedCategoriesWarning } from "@/components/UnmappedCategoriesWarning";
import { UploadStatusRow } from "@/components/UploadStatusRow";
import type { DashboardData, MonthHistoryEntry } from "@/lib/dashboard";
import { DASHBOARD_QUERY_KEY, fetchDashboard } from "@/lib/dashboard";
import { buildSettlementLabel, formatCurrency, MONTHS } from "@/lib/format";
import { usePersonMaps } from "@/lib/persons";
import { getPersonAccentColor } from "@/types/person";

function SummaryStats({
  data,
  personNames,
}: {
  data: DashboardData;
  personNames: Map<string, string>;
}) {
  const ytdLabel = buildSettlementLabel(data.ytd_settlement, personNames);

  return (
    <StatsGrid
      stats={[
        {
          label: "This month",
          value: formatCurrency(data.current_month_net_shared_spending),
        },
        {
          label: "Year to date",
          value: formatCurrency(data.ytd_total_shared_spending),
        },
        {
          label: "Year-to-date balance",
          value: ytdLabel,
        },
      ]}
    />
  );
}

function QuickActions() {
  return (
    <div className="flex items-center gap-3">
      <Link
        to="/upload"
        className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2.5 text-sm font-medium text-foreground shadow-sm transition-colors duration-150 hover:bg-muted"
      >
        <Upload className="size-4" />
        Upload CSV
      </Link>
      <Link
        to="/settle"
        className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2.5 text-sm font-medium text-foreground shadow-sm transition-colors duration-150 hover:bg-muted"
      >
        <HandCoins className="size-4" />
        Settle Up
      </Link>
      <Link
        to="/transactions"
        className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2.5 text-sm font-medium text-foreground shadow-sm transition-colors duration-150 hover:bg-muted"
      >
        View Transactions
        <ArrowRight className="size-4" />
      </Link>
    </div>
  );
}

function MonthHistory({
  entries,
  personNames,
}: {
  entries: MonthHistoryEntry[];
  personNames: Map<string, string>;
}) {
  const navigate = useNavigate();

  if (entries.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
      <h2 className="mb-4 font-medium text-lg text-foreground">
        Month History
      </h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="pb-2 pr-4 font-medium">Month</th>
            <th className="pb-2 pr-4 font-medium">Settlement</th>
            <th className="pb-2 text-right font-medium">Spending</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const monthName = MONTHS[entry.month - 1] ?? "";
            const label = buildHistorySettlementLabel(entry, personNames);

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
                <td className="py-2.5 pr-4 text-muted-foreground">{label}</td>
                <td className="py-2.5 text-right tabular-nums text-foreground">
                  {formatCurrency(entry.total_shared_spending)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function buildHistorySettlementLabel(
  entry: MonthHistoryEntry,
  personNames: Map<string, string>,
): string {
  if (entry.settlement_amount === 0 || !entry.settlement_from_person_id) {
    return "All settled";
  }
  const fromName =
    personNames.get(entry.settlement_from_person_id) ?? "Unknown";
  const toName = personNames.get(entry.settlement_to_person_id ?? "") ?? "";
  return `${fromName} owes ${toName} ${formatCurrency(entry.settlement_amount)}`;
}

export function DashboardPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: DASHBOARD_QUERY_KEY,
    queryFn: () => fetchDashboard(),
  });

  const { personNames, personIndexMap } = usePersonMaps(data?.persons);

  const monthLabel = data
    ? `${MONTHS[data.current_month_month - 1] ?? ""} ${data.current_month_year}`
    : "";
  const isEmpty =
    data &&
    data.current_month_transaction_count === 0 &&
    data.month_history.length === 0;

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
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

      {isLoading && <PageLoading label="Loading dashboard..." />}

      {error && <PageError error={error} onRetry={() => refetch()} />}

      {isEmpty && (
        <PageEmpty
          icon={<Upload />}
          heading={`No data for ${monthLabel}`}
          description="Upload a CSV to see your shared spending."
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
          {data.current_month_settlement &&
          data.current_month_settlement.amount > 0 ? (
            <Link
              to="/settle"
              className="block rounded-xl border border-primary/20 bg-card p-6 shadow-md transition-colors hover:bg-muted/50"
            >
              <p className="mb-1 text-center text-xs font-medium tracking-wider text-muted-foreground uppercase">
                {monthLabel}
              </p>
              <p className="text-center text-lg font-semibold text-foreground">
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-base font-semibold ${getPersonAccentColor(personIndexMap.get(data.current_month_settlement.from_person_id) ?? -1)}`}
                >
                  {personNames.get(
                    data.current_month_settlement.from_person_id,
                  ) ?? "Unknown"}
                </span>{" "}
                owes{" "}
                {personNames.get(data.current_month_settlement.to_person_id) ??
                  "Unknown"}{" "}
                <span className="tabular-nums">
                  {formatCurrency(data.current_month_settlement.amount)}
                </span>
              </p>
              <p className="mt-1 text-center text-sm text-primary">
                Settle Up <ArrowRight className="ml-1 inline size-3.5" />
              </p>
            </Link>
          ) : (
            <div className="rounded-xl border border-primary/20 bg-card p-6 shadow-md">
              <p className="mb-1 text-center text-xs font-medium tracking-wider text-muted-foreground uppercase">
                {monthLabel}
              </p>
              <p className="text-center text-lg font-semibold text-primary">
                <span className="inline-flex items-center gap-2">
                  <CheckCircle2 className="size-5" />
                  All settled!
                </span>
              </p>
            </div>
          )}
          <UploadStatusRow
            statuses={data.upload_statuses}
            personIndexMap={personIndexMap}
          />
          <SummaryStats data={data} personNames={personNames} />
          <QuickActions />
          <MonthHistory
            entries={data.month_history}
            personNames={personNames}
          />
          <UnmappedCategoriesWarning categories={data.unmapped_categories} />
        </div>
      )}
    </div>
  );
}
