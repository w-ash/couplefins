import {
  ArrowRight,
  CheckCircle2,
  Clock,
  HandCoins,
  LayoutDashboard,
  Lock,
  Upload,
} from "lucide-react";
import { Link, useNavigate } from "react-router";
import { useGetDashboard } from "@/api/generated/dashboard/dashboard";
import type {
  DashboardResponse,
  MonthHistoryEntryResponse,
} from "@/api/generated/model";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { PageEmpty, PageError, PageLoading } from "@/components/PageStates";
import { PersonBadge } from "@/components/PersonBadge";
import { StatsGrid } from "@/components/StatsGrid";
import { UnmappedCategoriesWarning } from "@/components/UnmappedCategoriesWarning";
import { UploadStatusRow } from "@/components/UploadStatusRow";
import { buildSettlementLabel, formatCurrency, MONTHS } from "@/lib/format";
import { actionLinkClass } from "@/lib/input-styles";
import { PAGE_PADDING } from "@/lib/layout";
import { usePersonMaps } from "@/lib/persons";

function SummaryStats({
  data,
  personNames,
}: {
  data: DashboardResponse;
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
        {
          label: "Settled this year",
          value: formatCurrency(data.ytd_total_settled),
        },
      ]}
    />
  );
}

function QuickActions() {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:gap-3">
      <Link to="/upload" className={actionLinkClass}>
        <Upload className="size-4" />
        Upload CSV
      </Link>
      <Link to="/settle" className={actionLinkClass}>
        <HandCoins className="size-4" />
        Settle Up
      </Link>
      <Link to="/transactions" className={actionLinkClass}>
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
  entries: MonthHistoryEntryResponse[];
  personNames: Map<string, string>;
}) {
  const navigate = useNavigate();

  if (entries.length === 0) return null;

  return (
    <Card>
      <h2 className="mb-1 font-medium text-lg text-foreground">
        Month History
      </h2>
      <p className="mb-4 text-xs text-muted-foreground">
        Track spending and settlement status across months
      </p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="pb-2 pr-4 font-medium">Month</th>
            <th className="pb-2 pr-4 font-medium">Settlement</th>
            <th className="hidden pb-2 text-right font-medium sm:table-cell">
              Spending
            </th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const monthName = MONTHS[entry.month - 1] ?? "";
            const label = buildSettlementLabel(
              entry.settlement_from_person_id
                ? {
                    amount: entry.settlement_amount,
                    from_person_id: entry.settlement_from_person_id,
                    to_person_id: entry.settlement_to_person_id ?? undefined,
                  }
                : null,
              personNames,
              { settledLabel: "All settled", includeToName: true },
            );

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
                    {entry.is_settled ? (
                      <CheckCircle2 className="size-3 text-positive" />
                    ) : entry.settlement_amount > 0 ? (
                      <Clock className="size-3 text-warning-muted-foreground" />
                    ) : null}
                    {label}
                  </span>
                </td>
                <td className="hidden py-2.5 text-right tabular-nums text-foreground sm:table-cell">
                  {formatCurrency(entry.total_shared_spending)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}

export function DashboardPage() {
  const { data: response, isLoading, error, refetch } = useGetDashboard();
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
    data.month_history.length === 0;

  return (
    <div className={`mx-auto max-w-4xl ${PAGE_PADDING}`}>
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
              className="block rounded-xl border border-primary/20 bg-card p-4 shadow-md transition-colors hover:bg-muted/50 sm:p-6"
            >
              <p className="mb-1 text-center text-xs font-medium tracking-wider text-muted-foreground uppercase">
                {monthLabel}
              </p>
              <p className="text-center text-base font-semibold text-foreground sm:text-lg">
                <PersonBadge
                  name={getPersonName(
                    data.current_month_settlement.from_person_id,
                  )}
                  accentColor={getPersonColor(
                    data.current_month_settlement.from_person_id,
                  )}
                  size="base"
                />{" "}
                owes {getPersonName(data.current_month_settlement.to_person_id)}{" "}
                <span className="tabular-nums">
                  {formatCurrency(data.current_month_settlement.amount)}
                </span>
              </p>
              <p className="mt-1 text-center text-sm text-primary">
                Settle Up <ArrowRight className="ml-1 inline size-3.5" />
              </p>
            </Link>
          ) : (
            <div className="rounded-xl border border-primary/20 bg-card p-4 shadow-md sm:p-6">
              <p className="mb-1 text-center text-xs font-medium tracking-wider text-muted-foreground uppercase">
                {monthLabel}
              </p>
              <p className="text-center text-base font-semibold text-primary sm:text-lg">
                <span className="inline-flex items-center gap-2">
                  <CheckCircle2 className="size-5" />
                  All settled!
                </span>
              </p>
            </div>
          )}
          <UploadStatusRow
            statuses={data.upload_statuses}
            getPersonColor={getPersonColor}
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
