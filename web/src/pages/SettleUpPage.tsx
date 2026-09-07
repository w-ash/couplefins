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
  LedgerYearResponse,
  MonthReference,
  SettlementPortionResponse,
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
  deriveSettlementDirection,
  type SelectedCandidate,
} from "@/components/CandidateChecklist";
import { Card } from "@/components/Card";
import { Dialog, DialogFooter, DialogHeader } from "@/components/Dialog";
import { ExpandChevron } from "@/components/ExpandChevron";
import { FinalizationBanner } from "@/components/FinalizationBanner";
import { InlineError } from "@/components/InlineError";
import { InlineSuccess } from "@/components/InlineSuccess";
import { LedgerMonthList, ledgerMonthKey } from "@/components/LedgerMonthList";
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
  MONTHS,
  plural,
  SHORT_MONTHS,
  useMonthYear,
} from "@/lib/format";
import { heroCardClass, PAGE_PADDING, tableHeaderRowClass } from "@/lib/layout";
import {
  defaultLedgerYear,
  findMonth,
  formatPortionPeriod,
  ledgerYears,
  settlementsTouching,
} from "@/lib/ledger";
import { usePersonMaps } from "@/lib/persons";

function HeroCard({
  years,
  yearRow,
  selectedYear,
  onYearChange,
  getPersonName,
  getPersonColor,
}: {
  years: number[];
  yearRow: LedgerYearResponse | null;
  selectedYear: number;
  onYearChange: (year: number) => void;
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
}) {
  const balance = yearRow?.balance ?? null;
  const charged = yearRow?.charged ?? null;
  const paid = yearRow?.paid ?? null;

  return (
    <section
      aria-label="Settlement summary"
      className={cn(heroCardClass, "p-5 sm:p-8")}
    >
      <div className="mb-4 flex justify-center">
        <SegmentedControl
          options={years.map((y) => ({ value: String(y), label: String(y) }))}
          value={String(selectedYear)}
          onChange={(value) => onYearChange(Number(value))}
          size="sm"
          shape="pill"
        />
      </div>

      {balance ? (
        <p className="text-center text-xl font-semibold text-foreground sm:text-2xl">
          <PersonBadge
            name={getPersonName(balance.from_person_id)}
            accentColor={getPersonColor(balance.from_person_id)}
            size="lg"
          />{" "}
          owes{" "}
          <PersonBadge
            name={getPersonName(balance.to_person_id)}
            accentColor={getPersonColor(balance.to_person_id)}
            size="lg"
          />{" "}
          <span className="tabular-nums">{formatCurrency(balance.amount)}</span>
        </p>
      ) : (
        <p className="text-center text-xl font-semibold text-primary sm:text-2xl">
          <span className="inline-flex items-center gap-2">
            <CheckCircle2 className="size-6" />
            {charged
              ? `${selectedYear} is settled`
              : `Nothing to settle in ${selectedYear}`}
          </span>
        </p>
      )}

      {yearRow?.span && (
        <p className="mt-2 text-center text-sm text-muted-foreground">
          covers {formatMonthSpan(yearRow.span)}
        </p>
      )}
      {/* The working line — the headline is never a bare number the couple
          has to take on trust. */}
      {paid && (
        <p className="mt-1 text-center text-sm text-muted-foreground tabular-nums">
          {formatCurrency(charged?.amount ?? 0)} charged,{" "}
          {formatCurrency(paid.amount)} paid in {selectedYear}
        </p>
      )}
    </section>
  );
}

function CoveredMonthsPicker({
  options,
  selectedKeys,
  onToggle,
}: {
  // The selected year's months, oldest first.
  options: LedgerMonthResponse[];
  selectedKeys: string[];
  onToggle: (key: string) => void;
}) {
  if (options.length === 0) return null;
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-muted-foreground">
        Covers — pick every month this payment settles
      </p>
      <div className="flex flex-wrap gap-1.5">
        {options.map((m) => {
          const key = ledgerMonthKey(m);
          const isSelected = selectedKeys.includes(key);
          return (
            <button
              key={key}
              type="button"
              aria-pressed={isSelected}
              onClick={() => onToggle(key)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isSelected
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {SHORT_MONTHS[m.month - 1]} {m.year}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function LinkSettlementSection({
  data,
  yearRow,
  monthsForYear,
  defaultMonth,
  getPersonName,
  onSuccess,
}: {
  data: SettleUpDataResponse;
  yearRow: LedgerYearResponse | null;
  monthsForYear: LedgerMonthResponse[];
  // The month the reader is drilled into — the 1:1 default coverage.
  defaultMonth: MonthReference;
  getPersonName: (id: string) => string;
  onSuccess: () => void;
}) {
  // Scoped to the selected year, so the amount searched for is the one the
  // hero shows.
  const direction = yearRow?.balance ?? null;

  const options = [...monthsForYear].sort((a, b) => a.month - b.month);
  // Default one portion at the currently viewed month; fall back to the
  // oldest month still carrying a balance.
  const defaultOption =
    options.find(
      (m) => m.year === defaultMonth.year && m.month === defaultMonth.month,
    ) ??
    options.find((m) => m.balance !== null) ??
    options[0];

  const [selected, setSelected] = useState<SelectedCandidate[]>([]);
  const [coveredKeys, setCoveredKeys] = useState<string[]>(
    defaultOption ? [ledgerMonthKey(defaultOption)] : [],
  );
  const [successMessage, setSuccessMessage] = useTemporary<string | null>(
    null,
    4000,
  );

  // Who actually paid whom, read from the selected legs — the
  // outstanding-balance direction is what is owed, not what happened.
  const derived = deriveSettlementDirection(selected, data.persons);

  const mutation = useRecordSettlement({
    mutation: {
      onSuccess: () => {
        if (derived) {
          const fromName = getPersonName(derived.from_person_id);
          const toName = getPersonName(derived.to_person_id);
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

  // Nothing to record when the year holds no balance.
  if (!direction) return null;

  const searchAmount = direction.amount.toFixed(2);
  const selectedIds = selected.map((c) => c.id);
  const amount = computeSettlementAmount(selected);
  const method = selected.length > 0 ? selected[0].merchant : "";
  const coveredMonths: MonthReference[] = options
    .filter((m) => coveredKeys.includes(ledgerMonthKey(m)))
    .map((m) => ({ year: m.year, month: m.month }));

  return (
    <Card>
      <CandidateChecklist
        amount={searchAmount}
        initialSearchMonth={null}
        searchFloor={yearRow?.span?.start ?? null}
        persons={data.persons}
        selectedIds={selectedIds}
        onSelectionChange={(_ids, candidates) => setSelected(candidates)}
        latestTransactionMonth={data.latest_transaction_month}
        defaultExpanded={false}
      />
      {selected.length > 0 && (
        <div className="mt-4 space-y-4">
          <CoveredMonthsPicker
            options={options}
            selectedKeys={coveredKeys}
            onToggle={(key) =>
              setCoveredKeys((prev) =>
                prev.includes(key)
                  ? prev.filter((k) => k !== key)
                  : [...prev, key],
              )
            }
          />
          <div className="flex items-center gap-3">
            <Button
              icon={<Link2 className="size-4" />}
              onClick={() => {
                if (!derived) return;
                mutation.mutate({
                  data: {
                    amount,
                    from_person_id: derived.from_person_id,
                    to_person_id: derived.to_person_id,
                    method,
                    linked_transaction_ids: selectedIds,
                    // The backend settles each of these months and stores
                    // the resulting portions.
                    covered_months: coveredMonths,
                  },
                });
              }}
              disabled={coveredMonths.length === 0 || derived === null}
              loading={mutation.isPending}
              loadingText="Linking..."
            >
              Mark as settlement ({formatCurrency(amount)})
            </Button>
          </div>
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
  yearRow,
  getPersonName,
  onSuccess,
}: {
  yearRow: LedgerYearResponse | null;
  getPersonName: (id: string) => string;
  onSuccess: (warnings: string[]) => void;
}) {
  const [confirmOpen, setConfirmOpen] = useState(false);

  const mutation = useWaiveSettlement({
    mutation: {
      onSuccess: (response) => {
        setConfirmOpen(false);
        onSuccess(response.status === 201 ? response.data.warnings : []);
      },
    },
  });

  const balance = yearRow?.balance ?? null;
  if (!yearRow || !balance) return null;

  const year = yearRow.year;
  const fromName = getPersonName(balance.from_person_id);
  const toName = getPersonName(balance.to_person_id);
  const amount = formatCurrency(balance.amount);

  return (
    <div className="rounded-lg border border-border-muted px-4 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">
            Waive {fromName}'s {year} balance
          </p>
          <p className="text-xs text-muted-foreground/70">
            Clears {amount} from {year} only. Undo by deleting the waiver.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setConfirmOpen(true)}
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
      {confirmOpen && (
        <Dialog size="sm" open onClose={() => setConfirmOpen(false)}>
          <DialogHeader
            title={`Waive the ${year} balance?`}
            onClose={() => setConfirmOpen(false)}
          />
          <p className="mt-3 text-sm text-muted-foreground">
            {fromName} owes {toName} {amount} for {year}. Waiving clears it;
            other years stay open.
          </p>
          <DialogFooter>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setConfirmOpen(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => {
                mutation.mutate({
                  data: {
                    waive_year: year,
                    from_person_id: balance.from_person_id,
                    to_person_id: balance.to_person_id,
                    notes: `${year} balance waived`,
                  },
                });
              }}
              loading={mutation.isPending}
              loadingText="Waiving..."
            >
              Waive Balance
            </Button>
          </DialogFooter>
        </Dialog>
      )}
    </div>
  );
}

// One line per portion: "$500.00 → Jan", or "$100.00 ← Feb" for a month the
// payment took value back from. Shown only when expanded — a lone portion
// always equals the settlement amount, which the Amount column already states.
function PortionBreakdown({
  portions,
  viewYear,
}: {
  portions: SettlementPortionResponse[];
  viewYear: number;
}) {
  return (
    <ul className="space-y-0.5 tabular-nums">
      {portions.map((p) => (
        <li key={`${p.year}-${p.month}`}>
          {formatCurrency(Math.abs(p.amount))} {p.amount < 0 ? "←" : "→"}{" "}
          {SHORT_MONTHS[p.month - 1]}
          {p.year === viewYear ? "" : ` ${p.year}`}
        </li>
      ))}
    </ul>
  );
}

// A pair of rows: the settlement, and its detail when expanded.
function SettlementHistoryRow({
  settlement,
  year,
  getPersonName,
  getPersonColor,
  onDelete,
  isDeleting,
  onOpenLinkDialog,
  isExpanded,
  onToggleExpand,
}: {
  settlement: LedgerSettlementResponse;
  year: number;
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
  onDelete: () => void;
  isDeleting: boolean;
  onOpenLinkDialog: () => void;
  isExpanded: boolean;
  onToggleExpand: () => void;
}) {
  const s = settlement;
  const fromName = getPersonName(s.from_person_id);
  const portions = s.portions ?? [];
  const period = formatPortionPeriod(portions, year);
  const linkCount = s.linked_transactions?.length ?? 0;
  // A lone portion needs no breakdown; notes are the other thing worth a look.
  const hasDetail = portions.length > 1 || s.notes !== "";

  return [
    <tr
      key="settlement"
      className="border-b border-border-muted transition-colors hover:bg-muted/50"
    >
      <td className="py-2 pr-4 whitespace-nowrap">
        {hasDetail ? (
          <button
            type="button"
            onClick={onToggleExpand}
            aria-expanded={isExpanded}
            className="flex min-h-11 items-center gap-1.5 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:min-h-0"
          >
            <ExpandChevron expanded={isExpanded} className="size-3.5" />
            {period}
          </button>
        ) : (
          <span className="ml-5">{period}</span>
        )}
      </td>
      <td className="py-2 pr-4">
        {s.is_waived ? (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            Waived
          </span>
        ) : (
          <PersonBadge
            name={fromName}
            accentColor={getPersonColor(s.from_person_id)}
            size="xs"
          />
        )}
      </td>
      <td className="py-2 pr-4 whitespace-nowrap text-muted-foreground">
        {formatShortDate(s.settled_at)}
        {s.method && <span className="capitalize"> · {s.method}</span>}
      </td>
      <td className="py-2 pr-4 text-right tabular-nums whitespace-nowrap">
        {formatCurrency(s.amount)}
      </td>
      <td className="py-2">
        <div className="flex items-center justify-end gap-1">
          {!s.is_waived && (
            <button
              type="button"
              onClick={onOpenLinkDialog}
              className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-primary transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={
                linkCount > 0
                  ? `View ${plural("linked transaction", linkCount)}`
                  : `Link a bank transaction to ${fromName} payment of ${formatCurrency(s.amount)}`
              }
            >
              <Link2 className="size-3.5" />
              {linkCount > 0 ? linkCount : "Link"}
            </button>
          )}
          <button
            type="button"
            onClick={onDelete}
            disabled={isDeleting}
            className="rounded-md p-2.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:p-1.5"
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
      </td>
    </tr>,
    hasDetail && isExpanded && (
      <tr key="detail" className="border-b border-border-muted bg-muted/30">
        <td colSpan={5} className="py-2 pl-5">
          <div className="editor-enter space-y-1 text-xs text-muted-foreground">
            {portions.length > 1 && (
              <PortionBreakdown portions={portions} viewYear={year} />
            )}
            {s.notes && <p>{s.notes}</p>}
          </div>
        </td>
      </tr>
    ),
  ];
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
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (settlements.length === 0) return null;

  const oldestFirst = [...settlements].sort((a, b) =>
    a.settled_at.localeCompare(b.settled_at),
  );

  return (
    <Card>
      <SectionHeader
        id="settlement-history"
        title="Settlement History"
        description={`Every payment and waiver covering ${year}, oldest first`}
      />
      <div className="overflow-x-auto">
        <table
          aria-labelledby="settlement-history"
          className="w-full border-spacing-0 text-sm"
        >
          <thead>
            <tr className={tableHeaderRowClass}>
              <th className="pb-2 pr-4 font-medium whitespace-nowrap">
                Period
              </th>
              <th className="pb-2 pr-4 font-medium">Payer</th>
              <th className="pb-2 pr-4 font-medium whitespace-nowrap">Paid</th>
              <th className="pb-2 pr-4 text-right font-medium">Amount</th>
              <th className="pb-2">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {oldestFirst.map((s) => (
              <SettlementHistoryRow
                key={s.id}
                settlement={s}
                year={year}
                getPersonName={getPersonName}
                getPersonColor={getPersonColor}
                onDelete={() => onDelete(s.id)}
                isDeleting={deletingId === s.id && isDeletionPending}
                onOpenLinkDialog={() => setLinkDialogSettlement(s)}
                isExpanded={expandedId === s.id}
                onToggleExpand={() =>
                  setExpandedId(expandedId === s.id ? null : s.id)
                }
              />
            ))}
          </tbody>
        </table>
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
    // the year-level sections must not flash back to a loading state.
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
  // it follows the API's year rows so a balance left over from an earlier
  // year is never hidden behind the current-year tab.
  const [pickedYear, setPickedYear] = useState<number | null>(null);
  const selectedYear = pickedYear ?? defaultLedgerYear(data?.years ?? []);
  const yearRow = data?.years.find((y) => y.year === selectedYear) ?? null;
  const monthsForYear =
    data?.months.filter((m) => m.year === selectedYear) ?? [];
  const settlementsForYear = settlementsTouching(
    data?.settlements ?? [],
    selectedYear,
  );

  const [deletingSettlementId, setDeletingSettlementId] = useState<
    string | null
  >(null);

  // Waiving hides WaiveAction on refetch (the balance goes to zero), so
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

  const months = data?.months;
  const hasExplicitMonth =
    searchParams.has("year") || searchParams.has("month");

  // Deep links open with their month expanded; the bare page defaults to
  // the current month's row — or jumps to the newest row when the current
  // month has no settlement activity.
  useEffect(() => {
    if (!months || hasExplicitMonth || months.length === 0) return;
    if (months.some((m) => m.year === year && m.month === month)) return;
    const newest = months[months.length - 1];
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("year", String(newest.year));
        next.set("month", String(newest.month));
        return next;
      },
      { replace: true },
    );
  }, [months, hasExplicitMonth, year, month, setSearchParams]);

  const rowForUrl = findMonth(months ?? [], year, month);
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
    data.settlements.length === 0 &&
    data.months.length === 0;

  // Single wiring for both drill-down entry points (the empty-month card and
  // the expanded month row) so finalize behavior can never diverge.
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
            years={ledgerYears(data.years)}
            yearRow={yearRow}
            selectedYear={selectedYear}
            onYearChange={setPickedYear}
            getPersonName={getPersonName}
            getPersonColor={getPersonColor}
          />

          {/* A selected month with no settlement activity still needs its
              audit, lock, and export controls (US-CLOSE-1/2) — the
              LedgerMonthList only covers months with activity. Skip this
              during the brief redirect to the newest row (months present, no
              explicit month yet) to avoid a flash. */}
          {!rowForUrl && (hasExplicitMonth || data.months.length === 0) && (
            <Card>
              {data.months.length > 0 && (
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
            months={monthsForYear}
            year={selectedYear}
            emptyLabel={
              data.months.length > 0
                ? `No settlement activity in ${selectedYear}.`
                : undefined
            }
            settlements={data.settlements}
            expandedKey={expandedKey}
            onToggle={handleToggle}
            getPersonName={getPersonName}
            getPersonColor={getPersonColor}
            renderExpanded={(m) => renderDrilldown(m.year, m.month)}
          />

          <SettlementHistory
            settlements={settlementsForYear}
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
            key={`${selectedYear}-${yearRow?.balance?.amount ?? 0}-${data.settlements.length}`}
            data={data}
            yearRow={yearRow}
            monthsForYear={monthsForYear}
            defaultMonth={{ year, month }}
            getPersonName={getPersonName}
            onSuccess={invalidateAll}
          />

          <WaiveAction
            yearRow={yearRow}
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
        </div>
      )}
    </div>
  );
}
