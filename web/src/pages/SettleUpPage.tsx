import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, HandCoins, Loader2, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/Button";
import { FinalizationBanner } from "@/components/FinalizationBanner";
import { MonthSelector } from "@/components/MonthSelector";
import { PageError, PageLoading } from "@/components/PageStates";
import { UploadStatusRow } from "@/components/UploadStatusRow";
import { DASHBOARD_QUERY_KEY } from "@/lib/dashboard";
import { formatCurrency, useMonthYear } from "@/lib/format";
import { usePersonMaps } from "@/lib/persons";
import { finalizePeriod, unfinalizePeriod } from "@/lib/reconciliation";
import type { SettlementRecord, SettleUpData } from "@/lib/settlements";
import {
  deleteSettlement,
  fetchSettleUpData,
  recordSettlement,
  SETTLE_UP_QUERY_KEY,
  waiveSettlement,
} from "@/lib/settlements";
import { getPersonAccentColor } from "@/types/person";

const formInputClass =
  "w-full rounded-lg border border-input bg-card px-3 py-2 text-sm text-foreground shadow-sm focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none";

function HeroCard({
  data,
  personNames,
  personIndexMap,
}: {
  data: SettleUpData;
  personNames: Map<string, string>;
  personIndexMap: Map<string, number>;
}) {
  const owed = data.owed;
  const isSettled = !owed || owed.amount === 0;

  if (isSettled) {
    return (
      <div className="rounded-xl border border-primary/20 bg-card p-8 shadow-md">
        <p className="text-center text-2xl font-semibold text-primary">
          <span className="inline-flex items-center gap-2">
            <CheckCircle2 className="size-6" />
            All settled!
          </span>
        </p>
      </div>
    );
  }

  const fromName = personNames.get(owed.from_person_id) ?? "Unknown";
  const toName = personNames.get(owed.to_person_id) ?? "Unknown";
  const fromColor = getPersonAccentColor(
    personIndexMap.get(owed.from_person_id) ?? -1,
  );

  return (
    <div className="rounded-xl border border-primary/20 bg-card p-8 shadow-md">
      <p className="text-center text-2xl font-semibold text-foreground">
        <span
          className={`inline-flex items-center justify-center rounded-full px-2.5 py-0.5 text-lg font-semibold ${fromColor}`}
        >
          {fromName}
        </span>{" "}
        owes {toName}{" "}
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

const METHODS = [
  { value: "venmo", label: "Venmo" },
  { value: "zelle", label: "Zelle" },
  { value: "other", label: "Other" },
];

function RecordPaymentForm({
  data,
  personNames,
  onSuccess,
}: {
  data: SettleUpData;
  personNames: Map<string, string>;
  onSuccess: () => void;
}) {
  const owed = data.owed;
  const defaultAmount =
    owed && data.remaining_balance > 0
      ? data.remaining_balance.toFixed(2)
      : (owed?.amount.toFixed(2) ?? "0");

  const [amount, setAmount] = useState(defaultAmount);
  const [method, setMethod] = useState("venmo");
  const [notes, setNotes] = useState("");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const successTimerRef = useRef<ReturnType<typeof setTimeout>>(null);

  useEffect(() => {
    return () => {
      if (successTimerRef.current) clearTimeout(successTimerRef.current);
    };
  }, []);

  const mutation = useMutation({
    mutationFn: () => {
      if (!owed) throw new Error("No balance owed");
      return recordSettlement({
        year: data.year,
        month: data.month,
        amount: Number.parseFloat(amount),
        from_person_id: owed.from_person_id,
        to_person_id: owed.to_person_id,
        method,
        notes,
      });
    },
    onSuccess: () => {
      const paidAmount = Number.parseFloat(amount);
      if (owed) {
        const fromName = personNames.get(owed.from_person_id) ?? "Unknown";
        const toName = personNames.get(owed.to_person_id) ?? "Unknown";
        setSuccessMessage(
          `Payment recorded — ${fromName} paid ${toName} ${formatCurrency(paidAmount)}`,
        );
        successTimerRef.current = setTimeout(
          () => setSuccessMessage(null),
          4000,
        );
      }
      setNotes("");
      onSuccess();
    },
  });

  if (!owed || owed.amount === 0) return null;

  const fromName = personNames.get(owed.from_person_id) ?? "Unknown";
  const toName = personNames.get(owed.to_person_id) ?? "Unknown";

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
      <h2 className="mb-4 font-medium text-lg text-foreground">
        Record Payment
      </h2>
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {fromName} pays {toName}
        </p>
        <div className="grid grid-cols-2 gap-4">
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
              onChange={(e) => setMethod(e.target.value)}
              className={formInputClass}
            >
              {METHODS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        </div>
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
        <Button
          onClick={() => mutation.mutate()}
          loading={mutation.isPending}
          loadingText="Recording..."
          disabled={!amount || Number.parseFloat(amount) <= 0}
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
          <p
            className="text-sm text-destructive"
            role="alert"
            aria-live="polite"
          >
            {mutation.error instanceof Error
              ? mutation.error.message
              : "Failed to record payment"}
          </p>
        )}
      </div>
    </div>
  );
}

function WaiveAction({
  data,
  personNames,
  onSuccess,
}: {
  data: SettleUpData;
  personNames: Map<string, string>;
  onSuccess: () => void;
}) {
  const owed = data.owed;

  const mutation = useMutation({
    mutationFn: () => {
      if (!owed) throw new Error("No balance owed");
      return waiveSettlement({
        year: data.year,
        month: data.month,
        from_person_id: owed.from_person_id,
        to_person_id: owed.to_person_id,
        notes: "Balance waived",
      });
    },
    onSuccess,
  });

  if (!owed || owed.amount === 0) return null;

  const fromName = personNames.get(owed.from_person_id) ?? "Unknown";

  return (
    <div className="rounded-lg border border-border-muted px-4 py-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">
            Waive {fromName}'s balance for this month
          </p>
          <p className="text-xs text-muted-foreground/70">
            The full balance will be forgiven. This can be undone by deleting
            the waiver.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => mutation.mutate()}
          loading={mutation.isPending}
        >
          Waive Balance
        </Button>
      </div>
      {mutation.isError && (
        <p
          className="mt-2 text-sm text-destructive"
          role="alert"
          aria-live="polite"
        >
          {mutation.error instanceof Error
            ? mutation.error.message
            : "Failed to waive balance"}
        </p>
      )}
    </div>
  );
}

function PaymentHistory({
  settlements,
  personNames,
  onDelete,
  isDeleting,
  isFinalized,
}: {
  settlements: SettlementRecord[];
  personNames: Map<string, string>;
  onDelete: (id: string) => void;
  isDeleting: boolean;
  isFinalized: boolean;
}) {
  if (settlements.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
      <h2 className="mb-4 font-medium text-lg text-foreground">
        Payment History
      </h2>
      <div className="space-y-3">
        {settlements.map((s) => {
          const fromName = personNames.get(s.from_person_id) ?? "Unknown";
          const toName = personNames.get(s.to_person_id) ?? "Unknown";
          const settledDate = new Date(s.settled_at).toLocaleDateString(
            "en-US",
            { month: "short", day: "numeric" },
          );

          return (
            <div
              key={s.id}
              className="flex items-center justify-between rounded-lg border border-border-muted px-4 py-3"
            >
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
                      <span className="ml-1.5 capitalize">via {s.method}</span>
                    )}
                    {s.notes && (
                      <span className="ml-1.5 text-muted-foreground/70">
                        — {s.notes}
                      </span>
                    )}
                  </p>
                </div>
              </div>
              {!isFinalized && (
                <button
                  type="button"
                  onClick={() => onDelete(s.id)}
                  disabled={isDeleting}
                  className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
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
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function SettleUpPage() {
  const { year, month } = useMonthYear();
  const queryClient = useQueryClient();

  const settleUpQueryKey = [...SETTLE_UP_QUERY_KEY, year, month];
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: settleUpQueryKey,
    queryFn: () => fetchSettleUpData(year, month),
  });

  const invalidateAll = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: SETTLE_UP_QUERY_KEY });
    queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY });
    queryClient.invalidateQueries({ queryKey: ["reconciliation"] });
  }, [queryClient]);

  const finalizeMutation = useMutation({
    mutationFn: () => finalizePeriod(year, month),
    onSuccess: invalidateAll,
  });

  const unfinalizeMutation = useMutation({
    mutationFn: () => unfinalizePeriod(year, month),
    onSuccess: invalidateAll,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSettlement(id),
    onSuccess: invalidateAll,
  });

  const { personNames, personIndexMap } = usePersonMaps(data?.persons);

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="flex items-center gap-2.5 font-semibold text-2xl text-foreground">
          <HandCoins className="size-6" />
          Settle Up
        </h1>
        <MonthSelector />
      </div>

      {isLoading && <PageLoading label="Loading settle up data..." />}

      {error && <PageError error={error} onRetry={() => refetch()} />}

      {data && (
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

          <UploadStatusRow
            statuses={data.upload_statuses}
            personIndexMap={personIndexMap}
          />

          <HeroCard
            data={data}
            personNames={personNames}
            personIndexMap={personIndexMap}
          />

          <RecordPaymentForm
            key={`${data.remaining_balance}-${data.recorded_settlements.length}`}
            data={data}
            personNames={personNames}
            onSuccess={invalidateAll}
          />

          <WaiveAction
            data={data}
            personNames={personNames}
            onSuccess={invalidateAll}
          />

          <PaymentHistory
            settlements={data.recorded_settlements}
            personNames={personNames}
            onDelete={(id) => deleteMutation.mutate(id)}
            isDeleting={deleteMutation.isPending}
            isFinalized={data.is_finalized}
          />
        </div>
      )}
    </div>
  );
}
