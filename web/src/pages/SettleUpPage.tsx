import { useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Download,
  HandCoins,
  Link2,
  Loader2,
  Trash2,
  Upload,
} from "lucide-react";
import { useCallback, useState } from "react";
import { getGetBudgetOverviewQueryKey } from "@/api/generated/budgets/budgets";
import { getGetDashboardQueryKey } from "@/api/generated/dashboard/dashboard";
import type {
  SettlementResponse,
  SettleUpDataResponse,
} from "@/api/generated/model";
import {
  getGetReconciliationQueryKey,
  useFinalizePeriod,
  useUnfinalizePeriod,
} from "@/api/generated/reconciliation/reconciliation";
import { useGetSettlementMerchants } from "@/api/generated/settings/settings";
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
import { CandidateChecklist } from "@/components/CandidateChecklist";
import { Card } from "@/components/Card";
import { FinalizationBanner } from "@/components/FinalizationBanner";
import { InlineError } from "@/components/InlineError";
import { LinkedTransactionSubrows } from "@/components/LinkedTransactionSubrows";
import { MonthPicker } from "@/components/MonthPicker";
import { PageHeader } from "@/components/PageHeader";
import {
  EmptyStateActions,
  PageEmpty,
  PageError,
  PageLoading,
} from "@/components/PageStates";
import { PersonBadge } from "@/components/PersonBadge";
import { PosthocLinkDialog } from "@/components/PosthocLinkDialog";
import { UploadStatusRow } from "@/components/UploadStatusRow";
import { useTemporary } from "@/hooks/useTemporary";
import { formatCurrency, MONTHS, useMonthYear } from "@/lib/format";
import { baseInputClass, selectInputClass } from "@/lib/input-styles";
import { PAGE_PADDING } from "@/lib/layout";
import { usePersonMaps } from "@/lib/persons";

const formInputClass = `w-full ${baseInputClass}`;
const formSelectClass = `w-full ${selectInputClass}`;

function HeroCard({
  data,
  getPersonName,
  getPersonColor,
}: {
  data: SettleUpDataResponse;
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
}) {
  const owed = data.owed;
  const isSettled = !owed || owed.amount === 0;

  if (isSettled) {
    return (
      <div className="rounded-xl border border-primary/20 bg-card p-5 shadow-md sm:p-8">
        <p className="text-center text-xl font-semibold text-primary sm:text-2xl">
          <span className="inline-flex items-center gap-2">
            <CheckCircle2 className="size-6" />
            All settled!
          </span>
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-primary/20 bg-card p-5 shadow-md sm:p-8">
      <p className="text-center text-xl font-semibold text-foreground sm:text-2xl">
        <PersonBadge
          name={getPersonName(owed.from_person_id)}
          accentColor={getPersonColor(owed.from_person_id)}
          size="lg"
        />{" "}
        owes{" "}
        <PersonBadge
          name={getPersonName(owed.to_person_id)}
          accentColor={getPersonColor(owed.to_person_id)}
          size="lg"
        />{" "}
        <span className="tabular-nums">{formatCurrency(owed.amount)}</span>
      </p>
      {data.remaining_balance > 0 && data.remaining_balance !== owed.amount && (
        <p className="mt-2 text-center text-sm text-muted-foreground">
          Remaining after payments:{" "}
          <span className="font-medium tabular-nums">
            {formatCurrency(data.remaining_balance)}
          </span>
        </p>
      )}
    </div>
  );
}

const OTHER_METHOD = "__other__";

function RecordPaymentForm({
  data,
  getPersonName,
  onSuccess,
}: {
  data: SettleUpDataResponse;
  getPersonName: (id: string) => string;
  onSuccess: () => void;
}) {
  const owed = data.owed;
  const defaultAmount =
    owed && data.remaining_balance > 0
      ? data.remaining_balance.toFixed(2)
      : (owed?.amount.toFixed(2) ?? "0");

  const { data: merchantsResponse } = useGetSettlementMerchants({
    query: { staleTime: Number.POSITIVE_INFINITY },
  });
  const merchants = merchantsResponse?.data ?? [];

  const [amount, setAmount] = useState(defaultAmount);
  const [selectedMethod, setSelectedMethod] = useState("");
  const [otherMethod, setOtherMethod] = useState("");
  const [notes, setNotes] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [successMessage, setSuccessMessage] = useTemporary<string | null>(
    null,
    4000,
  );

  const effectiveDefault = merchants.length > 0 ? merchants[0].name : "";
  const method = selectedMethod || effectiveDefault;

  const resolvedMethod = method === OTHER_METHOD ? otherMethod.trim() : method;

  const mutation = useRecordSettlement({
    mutation: {
      onSuccess: () => {
        const paidAmount = Number.parseFloat(amount);
        if (owed) {
          const fromName = getPersonName(owed.from_person_id);
          const toName = getPersonName(owed.to_person_id);
          setSuccessMessage(
            `Payment recorded — ${fromName} paid ${toName} ${formatCurrency(paidAmount)}`,
          );
        }
        setNotes("");
        setSelectedIds([]);
        onSuccess();
      },
    },
  });

  if (!owed || owed.amount === 0) return null;

  const fromName = getPersonName(owed.from_person_id);
  const toName = getPersonName(owed.to_person_id);

  return (
    <Card>
      <h2 className="mb-1 font-medium text-lg text-foreground">
        Record Payment
      </h2>
      <p className="mb-4 text-xs text-muted-foreground">
        Log a payment to reduce the outstanding balance
      </p>
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {fromName} pays {toName}
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="settlement-amount"
              className="mb-1 block text-sm font-medium text-foreground"
            >
              Amount
            </label>
            <input
              id="settlement-amount"
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={formInputClass}
            />
          </div>
          <div>
            <label
              htmlFor="settlement-method"
              className="mb-1 block text-sm font-medium text-foreground"
            >
              Method
            </label>
            <select
              id="settlement-method"
              value={method}
              onChange={(e) => setSelectedMethod(e.target.value)}
              className={formSelectClass}
            >
              {merchants.map((m) => (
                <option key={m.id} value={m.name}>
                  {m.name}
                </option>
              ))}
              <option value={OTHER_METHOD}>Other</option>
            </select>
          </div>
        </div>
        {method === OTHER_METHOD && (
          <div>
            <label
              htmlFor="settlement-method-other"
              className="mb-1 block text-sm font-medium text-foreground"
            >
              Payment method
            </label>
            <input
              id="settlement-method-other"
              type="text"
              value={otherMethod}
              onChange={(e) => setOtherMethod(e.target.value)}
              placeholder="e.g. Cash, bank transfer"
              className={formInputClass}
            />
          </div>
        )}
        <div>
          <label
            htmlFor="settlement-notes"
            className="mb-1 block text-sm font-medium text-foreground"
          >
            Notes (optional)
          </label>
          <input
            id="settlement-notes"
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g. Venmo confirmation #1234"
            className={formInputClass}
          />
        </div>
        <CandidateChecklist
          amount={amount}
          month={data.month}
          year={data.year}
          persons={data.persons}
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
        />
        <Button
          onClick={() => {
            if (!owed) return;
            mutation.mutate({
              data: {
                year: data.year,
                month: data.month,
                amount: Number.parseFloat(amount),
                from_person_id: owed.from_person_id,
                to_person_id: owed.to_person_id,
                method: resolvedMethod,
                notes,
                linked_transaction_ids:
                  selectedIds.length > 0 ? selectedIds : undefined,
              },
            });
          }}
          loading={mutation.isPending}
          loadingText="Recording..."
          disabled={
            !amount ||
            Number.parseFloat(amount) <= 0 ||
            (method === OTHER_METHOD && !otherMethod.trim())
          }
        >
          Record Payment
        </Button>
        {successMessage && (
          <p className="text-sm font-medium text-positive" aria-live="polite">
            <CheckCircle2 className="mr-1 inline size-3.5" />
            {successMessage}
          </p>
        )}
        {mutation.isError && (
          <InlineError>
            {mutation.error instanceof Error
              ? mutation.error.message
              : "Failed to record payment"}
          </InlineError>
        )}
      </div>
    </Card>
  );
}

function WaiveAction({
  data,
  getPersonName,
  onSuccess,
}: {
  data: SettleUpDataResponse;
  getPersonName: (id: string) => string;
  onSuccess: () => void;
}) {
  const owed = data.owed;

  const mutation = useWaiveSettlement({
    mutation: { onSuccess },
  });

  if (!owed || owed.amount === 0) return null;

  return (
    <div className="rounded-lg border border-border-muted px-4 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">
            Waive {getPersonName(owed.from_person_id)}'s balance for this month
          </p>
          <p className="text-xs text-muted-foreground/70">
            The full balance will be forgiven. This can be undone by deleting
            the waiver.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            if (!owed) return;
            mutation.mutate({
              data: {
                year: data.year,
                month: data.month,
                from_person_id: owed.from_person_id,
                to_person_id: owed.to_person_id,
                notes: "Balance waived",
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

function PaymentHistory({
  settlements,
  persons,
  getPersonName,
  getPersonColor,
  onDelete,
  deletingId,
  isDeletionPending,
  isFinalized,
  invalidateAll,
}: {
  settlements: SettlementResponse[];
  persons: Array<{ id: string; name: string }>;
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
  onDelete: (id: string) => void;
  deletingId: string | null;
  isDeletionPending: boolean;
  isFinalized: boolean;
  invalidateAll: () => void;
}) {
  const [linkDialogSettlement, setLinkDialogSettlement] =
    useState<SettlementResponse | null>(null);

  if (settlements.length === 0) return null;

  return (
    <Card>
      <h2 className="mb-1 font-medium text-lg text-foreground">
        Payment History
      </h2>
      <p className="mb-4 text-xs text-muted-foreground">
        Payments and waivers recorded for this month
      </p>
      <div className="space-y-3">
        {settlements.map((s) => {
          const fromName = getPersonName(s.from_person_id);
          const toName = getPersonName(s.to_person_id);
          const settledDate = new Date(s.settled_at).toLocaleDateString(
            "en-US",
            { month: "short", day: "numeric" },
          );
          const hasLinks = (s.linked_transactions?.length ?? 0) > 0;

          return (
            <div key={s.id}>
              <div className="flex items-start justify-between gap-2 rounded-lg border border-border-muted px-4 py-3">
                <div className="flex items-center gap-3">
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {s.is_waived ? (
                        <>Balance waived</>
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
                        <span className="ml-1.5 capitalize">
                          via {s.method}
                        </span>
                      )}
                      {s.notes && (
                        <span className="ml-1.5 text-muted-foreground/70">
                          — {s.notes}
                        </span>
                      )}
                    </p>
                    {!isFinalized && !s.is_waived && !hasLinks && (
                      <button
                        type="button"
                        onClick={() => setLinkDialogSettlement(s)}
                        className="mt-1 inline-flex items-center gap-1 text-xs text-primary transition-colors hover:text-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <Link2 className="size-3" />
                        Link bank transaction
                      </button>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {!isFinalized && (
                    <button
                      type="button"
                      onClick={() => onDelete(s.id)}
                      disabled={deletingId === s.id && isDeletionPending}
                      className="rounded-md p-2.5 sm:p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      aria-label={
                        s.is_waived
                          ? "Delete waiver"
                          : `Delete ${fromName} payment of ${formatCurrency(s.amount)}`
                      }
                    >
                      {deletingId === s.id && isDeletionPending ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <Trash2 className="size-4" />
                      )}
                    </button>
                  )}
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
        })}
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
        />
      )}
    </Card>
  );
}

export function SettleUpPage() {
  const { year, month } = useMonthYear();
  const queryClient = useQueryClient();

  const {
    data: settleUpResponse,
    isLoading,
    error,
    refetch,
  } = useGetSettleUpData(
    { year, month },
    { query: { refetchInterval: 5_000 } },
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

  const [deletingSettlementId, setDeletingSettlementId] = useState<
    string | null
  >(null);

  const deleteMutation = useDeleteSettlement({
    mutation: {
      onSuccess: () => {
        setDeletingSettlementId(null);
        invalidateAll();
      },
    },
  });

  const { getPersonName, getPersonColor } = usePersonMaps(data?.persons);

  const isEmpty =
    data &&
    data.transaction_count === 0 &&
    data.recorded_settlements.length === 0;

  const [exportOpen, setExportOpen] = useState(false);

  return (
    <div className={`mx-auto max-w-5xl ${PAGE_PADDING}`}>
      <PageHeader icon={<HandCoins className="size-6" />} title="Settle Up">
        <MonthPicker />
      </PageHeader>

      {isLoading && <PageLoading label="Loading settle up data..." />}

      {error && <PageError error={error} onRetry={() => refetch()} />}

      {data && (
        <UploadStatusRow
          statuses={data.upload_statuses}
          getPersonColor={getPersonColor}
        />
      )}

      {data && !isEmpty && <div className="h-2" />}

      {isEmpty && (
        <PageEmpty
          icon={<Upload />}
          heading={`No household transactions for ${MONTHS[month - 1]} ${year}`}
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
      )}

      {data && !isEmpty && (
        <div className="space-y-6">
          <FinalizationBanner
            isFinalized={data.is_finalized}
            finalizedAt={data.finalized_at}
            onFinalize={() =>
              finalizeMutation.mutate({
                data: { year, month, notes: "" },
              })
            }
            onUnfinalize={() =>
              unfinalizeMutation.mutate({
                data: { year, month },
              })
            }
            isPending={
              finalizeMutation.isPending || unfinalizeMutation.isPending
            }
          />

          <HeroCard
            data={data}
            getPersonName={getPersonName}
            getPersonColor={getPersonColor}
          />

          <RecordPaymentForm
            key={`${data.remaining_balance}-${data.recorded_settlements.length}`}
            data={data}
            getPersonName={getPersonName}
            onSuccess={invalidateAll}
          />

          <WaiveAction
            data={data}
            getPersonName={getPersonName}
            onSuccess={invalidateAll}
          />

          <PaymentHistory
            settlements={data.recorded_settlements}
            persons={data.persons}
            getPersonName={getPersonName}
            getPersonColor={getPersonColor}
            onDelete={(id) => {
              setDeletingSettlementId(id);
              deleteMutation.mutate({ settlementId: id });
            }}
            deletingId={deletingSettlementId}
            isDeletionPending={deleteMutation.isPending}
            isFinalized={data.is_finalized}
            invalidateAll={invalidateAll}
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
        </div>
      )}
    </div>
  );
}
