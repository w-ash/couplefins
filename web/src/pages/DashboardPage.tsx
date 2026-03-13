import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  LayoutDashboard,
  Lock,
  Upload,
} from "lucide-react";
import { useMemo } from "react";
import { Link, useNavigate } from "react-router";
import { FinalizationBanner } from "@/components/FinalizationBanner";
import { MonthSelector } from "@/components/MonthSelector";
import { PageEmpty, PageError, PageLoading } from "@/components/PageStates";
import { SettlementCard } from "@/components/SettlementCard";
import { UnmappedCategoriesWarning } from "@/components/UnmappedCategoriesWarning";
import type { DashboardData, MonthHistoryEntry } from "@/lib/dashboard";
import { DASHBOARD_QUERY_KEY, fetchDashboard } from "@/lib/dashboard";
import { formatCurrency, MONTHS, useMonthYear } from "@/lib/format";
import type { Settlement } from "@/lib/reconciliation";
import { finalizePeriod, unfinalizePeriod } from "@/lib/reconciliation";
import { getPersonAccentColor } from "@/types/person";

function UploadStatusRow({
  statuses,
  personIndexMap,
}: {
  statuses: DashboardData["upload_statuses"];
  personIndexMap: Map<string, number>;
}) {
  return (
    <div className="flex items-center justify-center gap-6">
      {statuses.map((s) => {
        const color = getPersonAccentColor(
          personIndexMap.get(s.person_id) ?? -1,
        );
        return (
          <div key={s.person_id} className="flex items-center gap-2 text-sm">
            {s.has_uploaded ? (
              <CheckCircle2 className="size-4 text-positive" />
            ) : (
              <Clock className="size-4 text-muted-foreground" />
            )}
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}
            >
              {s.person_name}
            </span>
            <span
              className={
                s.has_uploaded ? "text-foreground" : "text-muted-foreground"
              }
            >
              {s.has_uploaded ? "uploaded" : "not yet"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function SummaryStats({
  data,
  personNames,
}: {
  data: DashboardData;
  personNames: Map<string, string>;
}) {
  const ytdLabel = buildSettlementLabel(data.ytd_settlement, personNames);

  const stats = [
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
  ];

  return (
    <div className="grid grid-cols-3 gap-3">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="rounded-lg border border-border bg-card p-4 shadow-sm"
        >
          <p className="text-xs font-medium text-muted-foreground">
            {stat.label}
          </p>
          <p className="mt-1 text-lg font-semibold text-foreground tabular-nums text-right">
            {stat.value}
          </p>
        </div>
      ))}
    </div>
  );
}

function QuickActions({ year, month }: { year: number; month: number }) {
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
        to={`/transactions?year=${year}&month=${month}`}
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

function buildSettlementLabel(
  settlement: Settlement | null,
  personNames: Map<string, string>,
): string {
  if (!settlement || settlement.amount === 0) return "Settled";
  const fromName = personNames.get(settlement.from_person_id) ?? "Unknown";
  return `${fromName} owes ${formatCurrency(settlement.amount)}`;
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
  const { year, month } = useMonthYear();
  const queryClient = useQueryClient();

  const dashboardQueryKey = [...DASHBOARD_QUERY_KEY, year, month];
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: dashboardQueryKey,
    queryFn: () => fetchDashboard(year, month),
  });

  const finalizeMutation = useMutation({
    mutationFn: () => finalizePeriod(year, month),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ["reconciliation"] });
    },
  });

  const unfinalizeMutation = useMutation({
    mutationFn: () => unfinalizePeriod(year, month),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ["reconciliation"] });
    },
  });

  const { personNames, personIndexMap } = useMemo(() => {
    const persons = data?.persons ?? [];
    return {
      personNames: new Map(persons.map((p) => [p.id, p.name])),
      personIndexMap: new Map(persons.map((p, i) => [p.id, i])),
    };
  }, [data?.persons]);

  const monthName = MONTHS[month - 1] ?? "";
  const isEmpty =
    data &&
    data.current_month_transaction_count === 0 &&
    data.month_history.length === 0;

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="flex items-center gap-2.5 font-semibold text-2xl text-foreground">
          <LayoutDashboard className="size-6" />
          Dashboard
        </h1>
        <MonthSelector />
      </div>

      {isLoading && <PageLoading label="Loading dashboard..." />}

      {error && <PageError error={error} onRetry={() => refetch()} />}

      {isEmpty && (
        <PageEmpty
          icon={<Upload />}
          heading={`No data for ${monthName} ${year}`}
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
          <FinalizationBanner
            isFinalized={data.is_finalized}
            finalizedAt={data.finalized_at}
            onFinalize={() => finalizeMutation.mutate()}
            onUnfinalize={() => unfinalizeMutation.mutate()}
            isPending={
              finalizeMutation.isPending || unfinalizeMutation.isPending
            }
          />
          {data.current_month_settlement && (
            <SettlementCard
              settlement={data.current_month_settlement}
              personNames={personNames}
              personIndexMap={personIndexMap}
              periodLabel={`${monthName} ${year}`}
            />
          )}
          <UploadStatusRow
            statuses={data.upload_statuses}
            personIndexMap={personIndexMap}
          />
          <SummaryStats data={data} personNames={personNames} />
          <QuickActions year={year} month={month} />
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
