import { keepPreviousData, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Download,
  HandCoins,
  Link2,
  Loader2,
  Trash2,
  Upload,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { getGetBudgetOverviewQueryKey } from "@/api/generated/budgets/budgets";
import { getGetDashboardQueryKey } from "@/api/generated/dashboard/dashboard";
import type {
  LedgerMonthResponse,
  LedgerSettlementResponse,
  MonthReference,
  SettleUpDataResponse,
} from "@/api/generated/model";
import {
  getGetReconciliationQueryKey,
  useFinalizePeriod,
  useUnfinalizePeriod,
} from "@/api/generated/reconciliation/reconciliation";
import {
  getGetSettlementCandidatesQueryKey,
  getGetSettleUpDataQueryKey,
  useDeleteSettlement,
  useGetSettleUpData,
  useRecordSettlement,
  useWaiveSettlement,
} from "@/api/generated/settlements/settlements";
import { AdjustmentExportDialog } from "@/components/AdjustmentExportDialog";
import { Button } from "@/components/Button";
import {
  CandidateChecklist,
  computeSettlementAmount,
  type SelectedCandidate,
} from "@/components/CandidateChecklist";
import { Card } from "@/components/Card";
import { FinalizationBanner } from "@/components/FinalizationBanner";
import { InlineError } from "@/components/InlineError";
import { InlineSuccess } from "@/components/InlineSuccess";
import { LedgerMonthList, ledgerMonthKey } from "@/components/LedgerMonthList";
import { LinkedTransactionSubrows } from "@/components/LinkedTransactionSubrows";
import { PageHeader } from "@/components/PageHeader";
import {
  EmptyStateActions,
  PageEmpty,
  PageError,
  PageLoading,
} from "@/components/PageStates";
import { PersonBadge } from "@/components/PersonBadge";
import { PosthocLinkDialog } from "@/components/PosthocLinkDialog";
import { SectionHeader } from "@/components/SectionHeader";
import { SegmentedControl } from "@/components/SegmentedControl";
import { SettleUpAuditTable } from "@/components/SettleUpAuditTable";
import { UploadStatusRow } from "@/components/UploadStatusRow";
import { useTemporary } from "@/hooks/useTemporary";
import { cn } from "@/lib/cn";
import {
  formatCurrency,
  formatMonthSpan,
  formatShortDate,
  isZeroCurrency,
  MONTHS,
  SHORT_MONTHS,
  useMonthYear,
} from "@/lib/format";
import { heroCardClass, PAGE_PADDING } from "@/lib/layout";
import {
  defaultLedgerYear,
  type LedgerYearSummary,
  ledgerYears,
  settlementsForYear,
  summarizeLedgerYear,
} from "@/lib/ledger";
import { usePersonMaps } from "@/lib/persons";

function HeroCard({
  data,
  summary,
  onYearChange,
  getPersonName,
  getPersonColor,
}: {
  data: SettleUpDataResponse;
  summary: LedgerYearSummary;
  onYearChange: (year: number) => void;
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
}) {
  const year = summary.year;
  const years = ledgerYears(data.ledger_months);
  const outstanding = summary.outstanding;

  // Payments (and offsetting months) explain any gap between the year's
  // gross position and what it still owes.
  const gross = summary.gross;
  const hasPayments =
    gross !== null &&
    settlementsForYear(data.all_settlements, year).length > 0 &&
    (outstanding === null ||
      gross.from_person_id !== outstanding.from_person_id ||
      !isZeroCurrency(gross.amount - outstanding.amount));

  return (
    <section
      aria-label="Settlement summary"
      className={cn(heroCardClass, "p-5 sm:p-8")}
    >
      <div className="mb-4 flex justify-center">
        <SegmentedControl
          options={years.map((y) => ({ value: String(y), label: String(y) }))}
          value={String(year)}
          onChange={(value) => onYearChange(Number(value))}
          size="sm"
          shape="pill"
        />
      </div>

      {outstanding ? (
        <p className="text-center text-xl font-semibold text-foreground sm:text-2xl">
          <PersonBadge
            name={getPersonName(outstanding.from_person_id)}
            accentColor={getPersonColor(outstanding.from_person_id)}
            size="lg"
          />{" "}
          owes{" "}
          <PersonBadge
            name={getPersonName(outstanding.to_person_id)}
            accentColor={getPersonColor(outstanding.to_person_id)}
            size="lg"
          />{" "}
          <span className="tabular-nums">
            {formatCurrency(outstanding.amount)}
          </span>
        </p>
      ) : (
        <p className="text-center text-xl font-semibold text-primary sm:text-2xl">
          <span className="inline-flex items-center gap-2">
            <CheckCircle2 className="size-6" />
            {gross ? `${year} is settled` : `Nothing to settle in ${year}`}
          </span>
        </p>
      )}

      {summary.span && (
        <p className="mt-2 text-center text-sm text-muted-foreground">
          covers {formatMonthSpan(summary.span)}
        </p>
      )}
      {hasPayments && (
        <p className="mt-1 text-center text-sm text-muted-foreground">
          {formatCurrency(gross.amount)} gross, after payments
        </p>
      )}
    </section>
  );
}

function LinkSettlementSection({
  data,
  summary,
  getPersonName,
  onSuccess,
}: {
  data: SettleUpDataResponse;
  summary: LedgerYearSummary;
  getPersonName: (id: string) => string;
  onSuccess: () => void;
}) {
  // Scoped to the selected year, so the amount searched for is the one the
  // hero shows. The payment itself still lands on the running ledger.
  const direction = summary.outstanding;

  const [selected, setSelected] = useState<SelectedCandidate[]>([]);
  const [successMessage, setSuccessMessage] = useTemporary<string | null>(
    null,
    4000,
  );

  const mutation = useRecordSettlement({
    mutation: {
      onSuccess: () => {
        if (direction) {
          const fromName = getPersonName(direction.from_person_id);
          const toName = getPersonName(direction.to_person_id);
          const amount = computeSettlementAmount(selected);
          setSuccessMessage(
            `Settlement linked — ${fromName} paid ${toName} ${formatCurrency(amount)}`,
          );
        }
        setSelected([]);
        onSuccess();
      },
    },
  });

  // Payments are recorded against the running ledger — nothing to record
  // when nothing is outstanding.
  if (!direction) return null;

  const searchAmount = direction.amount.toFixed(2);
  const selectedIds = selected.map((c) => c.id);
  const amount = computeSettlementAmount(selected);
  const method = selected.length > 0 ? selected[0].merchant : "";

  return (
    <Card>
      <CandidateChecklist
        amount={searchAmount}
        initialSearchMonth={null}
        searchFloor={summary.span?.start ?? null}
        persons={data.persons}
        selectedIds={selectedIds}
        onSelectionChange={(_ids, candidates) => setSelected(candidates)}
        latestTransactionMonth={data.latest_transaction_month}
        defaultExpanded={false}
      />
      {selected.length > 0 && (
        <div className="mt-4 flex items-center gap-3">
          <Button
            icon={<Link2 className="size-4" />}
            onClick={() => {
              mutation.mutate({
                data: {
                  // Ledger-level payments carry no "recorded against" month.
                  year: null,
                  month: null,
                  amount,
                  from_person_id: direction.from_person_id,
                  to_person_id: direction.to_person_id,
                  method,
                  linked_transaction_ids: selectedIds,
                },
              });
            }}
            loading={mutation.isPending}
            loadingText="Linking..."
          >
            Mark as settlement ({formatCurrency(amount)})
          </Button>
        </div>
      )}
      {successMessage && (
        <div className="mt-3">
          <InlineSuccess>{successMessage}</InlineSuccess>
        </div>
      )}
      {mutation.isError && (
        <div className="mt-3">
          <InlineError>
            {mutation.error instanceof Error
              ? mutation.error.message
              : "Failed to link settlement"}
          </InlineError>
        </div>
      )}
    </Card>
  );
}

function WaiveAction({
  summary,
  getPersonName,
  onSuccess,
}: {
  summary: LedgerYearSummary;
  getPersonName: (id: string) => string;
  onSuccess: (warnings: string[]) => void;
}) {
  const year = summary.year;
  const outstanding = summary.outstanding;

  const mutation = useWaiveSettlement({
    mutation: {
      onSuccess: (response) => {
        onSuccess(response.status === 201 ? response.data.warnings : []);
      },
    },
  });

  if (!outstanding) return null;

  return (
    <div className="rounded-lg border border-border-muted px-4 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">
            Waive {getPersonName(outstanding.from_person_id)}'s {year} balance
          </p>
          <p className="text-xs text-muted-foreground/70">
            {formatCurrency(outstanding.amount)} from {year} will be forgiven.
            Other years are untouched, and this can be undone by deleting the
            waiver.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            mutation.mutate({
              data: {
                waive_year: year,
                from_person_id: outstanding.from_person_id,
                to_person_id: outstanding.to_person_id,
                notes: `${year} balance waived`,
              },
            });
          }}
          loading={mutation.isPending}
        >
          Waive Balance
        </Button>
      </div>
      {mutation.isError && (
        <div className="mt-2">
          <InlineError>
            {mutation.error instanceof Error
              ? mutation.error.message
              : "Failed to waive balance"}
          </InlineError>
        </div>
      )}
    </div>
  );
}

// "Mar" within the payment's own year, "Mar 2025" across years — compact
// coverage labels for one history row.
function coveredMonthLabel(
  covered: { year: number; month: number },
  settledYear: number,
): string {
  const name = SHORT_MONTHS[covered.month - 1];
  return covered.year === settledYear ? name : `${name} ${covered.year}`;
}

function SettlementHistoryRow({
  settlement,
  getPersonName,
  getPersonColor,
  onDelete,
  isDeleting,
  onOpenLinkDialog,
}: {
  settlement: LedgerSettlementResponse;
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
  onDelete: () => void;
  isDeleting: boolean;
  onOpenLinkDialog: () => void;
}) {
  const s = settlement;
  const fromName = getPersonName(s.from_person_id);
  const toName = getPersonName(s.to_person_id);
  const settledDate = formatShortDate(s.settled_at);
  const settledYear = Number(s.settled_at.slice(0, 4));
  const hasLinks = (s.linked_transactions?.length ?? 0) > 0;

  const coverage =
    s.covered.length > 0
      ? `Covered ${s.covered
          .map((c) => coveredMonthLabel(c, settledYear))
          .join(" + ")}`
      : null;

  return (
    <div>
      <div className="flex items-start justify-between gap-2 rounded-lg border border-border-muted px-4 py-3">
        <div className="flex items-center gap-3">
          <div>
            <p className="text-sm font-medium text-foreground">
              {s.is_waived ? (
                <>
                  Balance waived{" "}
                  <span className="tabular-nums">
                    {formatCurrency(s.amount)}
                  </span>
                </>
              ) : (
                <>
                  {fromName} paid {toName}{" "}
                  <span className="tabular-nums">
                    {formatCurrency(s.amount)}
                  </span>
                </>
              )}
            </p>
            <p className="text-xs text-muted-foreground">
              {settledDate}
              {s.method && (
                <span className="ml-1.5 capitalize">via {s.method}</span>
              )}
              {s.year !== null && s.month !== null && (
                <span className="ml-1.5 text-muted-foreground/70">
                  · recorded against {MONTHS[s.month - 1]}
                  {s.year !== settledYear ? ` ${s.year}` : ""}
                </span>
              )}
              {s.notes && (
                <span className="ml-1.5 text-muted-foreground/70">
                  — {s.notes}
                </span>
              )}
            </p>
            {coverage && (
              <p className="text-xs text-muted-foreground">{coverage}</p>
            )}
            {s.unapplied > 0 && (
              <p className="text-xs text-warning-muted-foreground">
                {formatCurrency(s.unapplied)} not applied — increases the
                balance
              </p>
            )}
            {!s.is_waived && !hasLinks && (
              <button
                type="button"
                onClick={onOpenLinkDialog}
                className="mt-1 inline-flex items-center gap-1 text-xs text-primary transition-colors hover:text-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Link2 className="size-3" />
                Link bank transaction
              </button>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onDelete}
            disabled={isDeleting}
            className="rounded-md p-2.5 sm:p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={
              s.is_waived
                ? "Delete waiver"
                : `Delete ${fromName} payment of ${formatCurrency(s.amount)}`
            }
          >
            {isDeleting ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Trash2 className="size-4" />
            )}
          </button>
        </div>
      </div>
      {hasLinks && s.linked_transactions && (
        <LinkedTransactionSubrows
          linkedTransactions={s.linked_transactions}
          getPersonName={getPersonName}
          getPersonColor={getPersonColor}
        />
      )}
    </div>
  );
}

function SettlementHistory({
  settlements,
  year,
  persons,
  getPersonName,
  getPersonColor,
  onDelete,
  deletingId,
  isDeletionPending,
  invalidateAll,
  latestTransactionMonth,
}: {
  // Already scoped to `year` by the caller.
  settlements: LedgerSettlementResponse[];
  year: number;
  persons: Array<{ id: string; name: string }>;
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
  onDelete: (id: string) => void;
  deletingId: string | null;
  isDeletionPending: boolean;
  invalidateAll: () => void;
  latestTransactionMonth: MonthReference | null;
}) {
  const [linkDialogSettlement, setLinkDialogSettlement] =
    useState<LedgerSettlementResponse | null>(null);

  if (settlements.length === 0) return null;

  return (
    <Card>
      <SectionHeader
        title="Settlement History"
        description={`Every payment and waiver covering ${year}, oldest first`}
      />
      <div className="space-y-3">
        {settlements.map((s) => (
          <SettlementHistoryRow
            key={s.id}
            settlement={s}
            getPersonName={getPersonName}
            getPersonColor={getPersonColor}
            onDelete={() => onDelete(s.id)}
            isDeleting={deletingId === s.id && isDeletionPending}
            onOpenLinkDialog={() => setLinkDialogSettlement(s)}
          />
        ))}
      </div>

      {linkDialogSettlement && (
        <PosthocLinkDialog
          open={linkDialogSettlement !== null}
          onClose={() => setLinkDialogSettlement(null)}
          settlement={linkDialogSettlement}
          persons={persons}
          getPersonName={getPersonName}
          getPersonColor={getPersonColor}
          onSuccess={invalidateAll}
          latestTransactionMonth={latestTransactionMonth}
        />
      )}
    </Card>
  );
}

// Month-scoped drill-down content (audit, upload status, lock, export). Keyed
// on a plain {year, month} so it also serves a selected month that has no
// ledger row (household/personal-only spending): those months still need to be
// lockable and exportable (US-CLOSE-1/2), even without settlement activity.
function MonthDrilldown({
  year,
  month,
  data,
  personNames,
  getPersonColor,
  onFinalize,
  onUnfinalize,
  isFinalizePending,
}: {
  year: number;
  month: number;
  data: SettleUpDataResponse;
  personNames: Map<string, string>;
  getPersonColor: (id: string) => string;
  onFinalize: () => void;
  onUnfinalize: () => void;
  isFinalizePending: boolean;
}) {
  const [exportOpen, setExportOpen] = useState(false);

  // Month-scoped fields lag one fetch behind while the drill-down month
  // loads (keepPreviousData) — don't render another month's numbers here.
  const isReady = data.year === year && data.month === month;
  if (!isReady) {
    return (
      <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        Loading {MONTHS[month - 1]}...
      </div>
    );
  }

  return (
    <>
      <UploadStatusRow
        statuses={data.upload_statuses}
        getPersonColor={getPersonColor}
      />

      <SettleUpAuditTable data={data} personNames={personNames} />

      <FinalizationBanner
        isFinalized={data.is_finalized}
        finalizedAt={data.finalized_at}
        onFinalize={onFinalize}
        onUnfinalize={onUnfinalize}
        isPending={isFinalizePending}
        warnings={data.finalization_warnings}
      />

      <button
        type="button"
        onClick={() => setExportOpen(true)}
        className="inline-flex items-center gap-1.5 rounded text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Download className="size-3.5" />
        Export adjustments to Monarch
      </button>

      <AdjustmentExportDialog
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        year={year}
        month={month}
      />
    </>
  );
}

export function SettleUpPage() {
  const { year, month } = useMonthYear();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();

  const {
    data: settleUpResponse,
    isLoading,
    error,
    refetch,
  } = useGetSettleUpData(
    { year, month },
    // keepPreviousData: drilling into a month refetches with new params —
    // the ledger-level sections must not flash back to a loading state.
    { query: { refetchInterval: 5_000, placeholderData: keepPreviousData } },
  );
  const data =
    settleUpResponse?.status === 200 ? settleUpResponse.data : undefined;

  const invalidateAll = useCallback(() => {
    queryClient.invalidateQueries({
      queryKey: getGetSettleUpDataQueryKey(),
    });
    queryClient.invalidateQueries({ queryKey: getGetDashboardQueryKey() });
    queryClient.invalidateQueries({
      queryKey: getGetReconciliationQueryKey(),
    });
    queryClient.invalidateQueries({
      queryKey: getGetBudgetOverviewQueryKey(),
    });
    queryClient.invalidateQueries({
      queryKey: getGetSettlementCandidatesQueryKey(),
    });
  }, [queryClient]);

  const finalizeMutation = useFinalizePeriod({
    mutation: { onSuccess: invalidateAll },
  });

  const unfinalizeMutation = useUnfinalizePeriod({
    mutation: { onSuccess: invalidateAll },
  });

  // The page summarizes a whole calendar year, independent of the month
  // drill-down the ?year/?month params drive. Until the reader picks a year,
  // it follows the ledger so a balance carried over from an earlier year is
  // never hidden behind the current-year tab.
  const [pickedYear, setPickedYear] = useState<number | null>(null);
  const selectedYear =
    pickedYear ?? defaultLedgerYear(data?.ledger_months ?? []);
  const yearSummary = summarizeLedgerYear(
    data?.ledger_months ?? [],
    selectedYear,
  );

  const [deletingSettlementId, setDeletingSettlementId] = useState<
    string | null
  >(null);

  // Waiving hides WaiveAction on refetch (outstanding goes to zero), so
  // its warnings must outlive the component.
  const [waiveWarnings, setWaiveWarnings] = useTemporary<string[] | null>(
    null,
    8000,
  );

  const deleteMutation = useDeleteSettlement({
    mutation: {
      onSuccess: () => {
        setDeletingSettlementId(null);
        invalidateAll();
      },
    },
  });

  const { personNames, getPersonName, getPersonColor } = usePersonMaps(
    data?.persons,
  );

  const ledgerMonths = data?.ledger_months;
  const hasExplicitMonth =
    searchParams.has("year") || searchParams.has("month");

  // Deep links open with their month expanded; the bare page defaults to
  // the current month's row — or jumps to the newest row when the current
  // month has no ledger activity.
  useEffect(() => {
    if (!ledgerMonths || hasExplicitMonth || ledgerMonths.length === 0) return;
    if (ledgerMonths.some((m) => m.year === year && m.month === month)) return;
    const newest = ledgerMonths[ledgerMonths.length - 1];
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("year", String(newest.year));
        next.set("month", String(newest.month));
        return next;
      },
      { replace: true },
    );
  }, [ledgerMonths, hasExplicitMonth, year, month, setSearchParams]);

  const rowForUrl =
    ledgerMonths?.find((m) => m.year === year && m.month === month) ?? null;
  const derivedKey = rowForUrl ? ledgerMonthKey(rowForUrl) : null;
  const [collapsedKey, setCollapsedKey] = useState<string | null>(null);
  const expandedKey =
    derivedKey !== null && collapsedKey !== derivedKey ? derivedKey : null;

  const handleToggle = useCallback(
    (m: LedgerMonthResponse) => {
      const key = ledgerMonthKey(m);
      if (expandedKey === key) {
        setCollapsedKey(key);
        return;
      }
      setCollapsedKey(null);
      if (key !== derivedKey) {
        setSearchParams((prev) => {
          const next = new URLSearchParams(prev);
          next.set("year", String(m.year));
          next.set("month", String(m.month));
          return next;
        });
      }
    },
    [expandedKey, derivedKey, setSearchParams],
  );

  const isEmpty =
    data &&
    data.transaction_count === 0 &&
    data.all_settlements.length === 0 &&
    data.ledger_months.length === 0;

  // Single wiring for both drill-down entry points (the empty-month card and
  // the expanded ledger row) so finalize behavior can never diverge.
  const renderDrilldown = (drillYear: number, drillMonth: number) =>
    data && (
      <MonthDrilldown
        year={drillYear}
        month={drillMonth}
        data={data}
        personNames={personNames}
        getPersonColor={getPersonColor}
        onFinalize={() =>
          finalizeMutation.mutate({
            data: { year: drillYear, month: drillMonth, notes: "" },
          })
        }
        onUnfinalize={() =>
          unfinalizeMutation.mutate({
            data: { year: drillYear, month: drillMonth },
          })
        }
        isFinalizePending={
          finalizeMutation.isPending || unfinalizeMutation.isPending
        }
      />
    );

  return (
    <div className={`mx-auto max-w-5xl ${PAGE_PADDING}`}>
      <PageHeader icon={<HandCoins className="size-6" />} title="Settle Up" />

      {isLoading && <PageLoading label="Loading settle up data..." />}

      {error && <PageError error={error} onRetry={() => refetch()} />}

      {isEmpty && data && (
        <>
          <UploadStatusRow
            statuses={data.upload_statuses}
            getPersonColor={getPersonColor}
          />
          <PageEmpty
            icon={<Upload />}
            heading={`No transactions to settle for ${MONTHS[month - 1]} ${year}`}
            description="Upload a CSV to get started with settlement."
            action={
              <EmptyStateActions
                latestMonth={data.latest_transaction_month}
                currentYear={year}
                currentMonth={month}
                viewPath="settle"
              />
            }
          />
        </>
      )}

      {data && !isEmpty && (
        <div className="space-y-6">
          <HeroCard
            data={data}
            summary={yearSummary}
            onYearChange={setPickedYear}
            getPersonName={getPersonName}
            getPersonColor={getPersonColor}
          />

          <WaiveAction
            summary={yearSummary}
            getPersonName={getPersonName}
            onSuccess={(warnings) => {
              setWaiveWarnings(warnings.length > 0 ? warnings : null);
              invalidateAll();
            }}
          />

          {waiveWarnings && (
            <ul className="space-y-0.5 rounded-lg border border-border-muted px-4 py-3">
              {waiveWarnings.map((w) => (
                <li key={w} className="text-xs text-warning-muted-foreground">
                  {w}
                </li>
              ))}
            </ul>
          )}

          {/* A selected month with no ledger row still needs its audit,
              lock, and export controls (US-CLOSE-1/2) — the LedgerMonthList
              only covers months with settlement activity. Skip this during
              the brief redirect to the newest row (ledger present, no explicit
              month yet) to avoid a flash. */}
          {!rowForUrl &&
            (hasExplicitMonth || data.ledger_months.length === 0) && (
              <Card>
                {data.ledger_months.length > 0 && (
                  <p className="mb-4 text-sm text-muted-foreground">
                    No settlement activity for {MONTHS[month - 1]} {year} —
                    nothing to settle, but you can still review and lock the
                    month.
                  </p>
                )}
                <div className="space-y-4">{renderDrilldown(year, month)}</div>
              </Card>
            )}

          <LedgerMonthList
            months={data.ledger_months.filter((m) => m.year === selectedYear)}
            year={selectedYear}
            emptyLabel={
              data.ledger_months.length > 0
                ? `No settlement activity in ${selectedYear}.`
                : undefined
            }
            settlements={data.all_settlements}
            expandedKey={expandedKey}
            onToggle={handleToggle}
            getPersonName={getPersonName}
            getPersonColor={getPersonColor}
            renderExpanded={(m) => renderDrilldown(m.year, m.month)}
          />

          <SettlementHistory
            settlements={settlementsForYear(data.all_settlements, selectedYear)}
            year={selectedYear}
            persons={data.persons}
            getPersonName={getPersonName}
            getPersonColor={getPersonColor}
            onDelete={(id) => {
              setDeletingSettlementId(id);
              deleteMutation.mutate({ settlementId: id });
            }}
            deletingId={deletingSettlementId}
            isDeletionPending={deleteMutation.isPending}
            invalidateAll={invalidateAll}
            latestTransactionMonth={data.latest_transaction_month}
          />

          <LinkSettlementSection
            key={`${selectedYear}-${yearSummary.outstanding?.amount ?? 0}-${data.all_settlements.length}`}
            data={data}
            summary={yearSummary}
            getPersonName={getPersonName}
            onSuccess={invalidateAll}
          />
        </div>
      )}
    </div>
  );
}
