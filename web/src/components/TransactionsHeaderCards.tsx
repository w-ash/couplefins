import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  HandCoins,
  Lock,
} from "lucide-react";
import type { ReactNode } from "react";
import { useMemo } from "react";
import { Link } from "react-router";
import type {
  OwedAmountResponse,
  ReconciliationResponse,
  SettleUpDataResponse,
  TransactionResponse,
} from "@/api/generated/model";
import { useGetSettleUpData } from "@/api/generated/settlements/settlements";
import { Card } from "@/components/Card";
import { InfoPopover } from "@/components/InfoPopover";
import { cn } from "@/lib/cn";
import {
  buildSettlementLabel,
  formatCurrency,
  isZeroCurrency,
  plural,
} from "@/lib/format";
import {
  bucketTransactions,
  SCOPE_LABELS,
  sumNet,
  type TransactionScope,
} from "@/lib/transaction-filters";

interface SharedHeaderProps {
  data: ReconciliationResponse;
  filtered: TransactionResponse[];
  scope: TransactionScope;
  currentPersonId: string | null;
  personNames: Map<string, string>;
  periodLabel: string;
  singleMonth: { year: number; month: number } | null;
  settlementChipActive: boolean;
  onShowSettlements: () => void;
}

export function TransactionsHeaderCards({
  data,
  filtered,
  scope,
  currentPersonId,
  personNames,
  periodLabel,
  singleMonth,
  settlementChipActive,
  onShowSettlements,
}: SharedHeaderProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <SettlementCard
        data={data}
        personNames={personNames}
        singleMonth={singleMonth}
        settlementChipActive={settlementChipActive}
        onShowSettlements={onShowSettlements}
      />
      <ImportedCard
        data={data}
        currentPersonId={currentPersonId}
        periodLabel={periodLabel}
      />
      <InViewCard
        data={data}
        filtered={filtered}
        scope={scope}
        periodLabel={periodLabel}
      />
    </div>
  );
}

interface SettlementCardProps {
  data: ReconciliationResponse;
  personNames: Map<string, string>;
  singleMonth: { year: number; month: number } | null;
  settlementChipActive: boolean;
  onShowSettlements: () => void;
}

function SettlementCard({
  data,
  personNames,
  singleMonth,
  settlementChipActive,
  onShowSettlements,
}: SettlementCardProps) {
  const settleUp = useSettleUpForMonth(singleMonth);

  return (
    <CardShell
      label="Settlement"
      info={
        <SettlementInfo
          hasSettleUp={settleUp.kind === "ready"}
          singleMonth={singleMonth !== null}
        />
      }
    >
      {settleUp.kind === "ready" ? (
        <SettlementBalance
          settleUp={settleUp.data}
          grossFallback={data.settlement ?? null}
          personNames={personNames}
          settlementChipActive={settlementChipActive}
          onShowSettlements={onShowSettlements}
        />
      ) : (
        <SettlementPlaceholder
          kind={settleUp.kind}
          gross={data.settlement ?? null}
          personNames={personNames}
        />
      )}
      {singleMonth !== null && (
        <Link
          to={`/settle?${new URLSearchParams({
            year: String(singleMonth.year),
            month: String(singleMonth.month),
          })}`}
          className="mt-1 inline-flex items-center gap-0.5 text-[11px] font-medium text-primary hover:underline"
        >
          View on Settle Up
          <ArrowRight className="size-3" />
        </Link>
      )}
    </CardShell>
  );
}

function SettlementBalance({
  settleUp,
  grossFallback,
  personNames,
  settlementChipActive,
  onShowSettlements,
}: {
  settleUp: SettleUpDataResponse;
  grossFallback: OwedAmountResponse | null;
  personNames: Map<string, string>;
  settlementChipActive: boolean;
  onShowSettlements: () => void;
}) {
  const netDirection = settleUp.net_position ?? null;
  const grossDirection = settleUp.owed ?? grossFallback;
  const linked = settleUp.recorded_settlements ?? [];
  const linkedTotal = linked.reduce((s, x) => s + x.amount, 0);
  const linkedCount = linked.length;
  const isSettled = !netDirection || isZeroCurrency(netDirection.amount);
  const canFilter = linkedCount > 0;

  const description = settlementDescription({
    isSettled,
    grossDirection,
    linkedCount,
    linkedTotal,
  });

  return (
    <>
      <button
        type="button"
        onClick={onShowSettlements}
        disabled={!canFilter}
        aria-pressed={canFilter ? settlementChipActive : undefined}
        className={cn(
          "text-left text-lg font-semibold tabular-nums",
          isSettled ? "text-positive" : "text-foreground",
          canFilter &&
            "decoration-dotted underline-offset-2 hover:underline focus-visible:underline focus-visible:outline-none",
          // Active state: solid underline + primary tint, distinct from hover.
          settlementChipActive &&
            canFilter &&
            "text-primary underline decoration-solid",
        )}
        title={
          canFilter
            ? `Show the ${plural("linked settlement", linkedCount)} below`
            : undefined
        }
      >
        {buildSettlementLabel(netDirection, personNames, {
          includeToName: true,
          settledLabel: "Settled",
        })}
      </button>
      {description && (
        <p className="text-[11px] leading-tight text-muted-foreground/70">
          {description}
        </p>
      )}
    </>
  );
}

// A "Settled" headline requires actual settle-up data confirming the net
// position — without it, render an honest placeholder instead.
function SettlementPlaceholder({
  kind,
  gross,
  personNames,
}: {
  kind: "disabled" | "loading" | "error";
  gross: OwedAmountResponse | null;
  personNames: Map<string, string>;
}) {
  const showGross =
    kind === "error" && gross !== null && !isZeroCurrency(gross.amount);
  return (
    <>
      <p
        className={cn(
          "text-lg font-semibold tabular-nums",
          showGross ? "text-foreground" : "text-muted-foreground",
        )}
      >
        {showGross
          ? buildSettlementLabel(gross, personNames, { includeToName: true })
          : "—"}
      </p>
      {kind === "disabled" && (
        <p className="text-[11px] leading-tight text-muted-foreground/70">
          Select a single month to see settlement balance
        </p>
      )}
      {kind === "error" && (
        <p className="text-[11px] leading-tight text-muted-foreground/70">
          {showGross
            ? "Showing gross — settle-up data unavailable"
            : "Settle-up data unavailable"}
        </p>
      )}
    </>
  );
}

function settlementDescription(args: {
  isSettled: boolean;
  grossDirection: OwedAmountResponse | null;
  linkedCount: number;
  linkedTotal: number;
}): string | null {
  const { isSettled, grossDirection, linkedCount, linkedTotal } = args;
  if (isSettled) {
    if (linkedCount > 0) {
      return `${plural("settlement", linkedCount)} linked · ${formatCurrency(linkedTotal)}`;
    }
    if (!grossDirection || isZeroCurrency(grossDirection.amount)) {
      return "No transactions to settle this period";
    }
    return "Fully paid";
  }
  if (grossDirection) {
    if (linkedCount > 0) {
      return `Gross ${formatCurrency(grossDirection.amount)} · ${plural("payment", linkedCount)} linked (${formatCurrency(linkedTotal)})`;
    }
    return "Gross from this period · no settlements linked yet";
  }
  return null;
}

type SettleUpForMonth =
  | { kind: "disabled" }
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; data: SettleUpDataResponse };

function useSettleUpForMonth(
  singleMonth: { year: number; month: number } | null,
): SettleUpForMonth {
  const enabled = singleMonth !== null;
  // Fallback params are inert because `enabled: false` short-circuits the request.
  const params = singleMonth ?? { year: 1970, month: 1 };
  const { data, isPending } = useGetSettleUpData(params, {
    query: { enabled, refetchInterval: enabled ? 5_000 : false },
  });
  // Disabled queries stay pending forever, so this check must come first.
  if (!enabled) return { kind: "disabled" };
  if (data?.status === 200) return { kind: "ready", data: data.data };
  // isPending (not isFetching) so background polls don't flash the card back to loading.
  if (isPending) return { kind: "loading" };
  return { kind: "error" };
}

interface ImportedCardProps {
  data: ReconciliationResponse;
  currentPersonId: string | null;
  periodLabel: string;
}

function ImportedCard({
  data,
  currentPersonId,
  periodLabel,
}: ImportedCardProps) {
  const buckets = useMemo(
    () => bucketTransactions(data.transactions, currentPersonId),
    [data.transactions, currentPersonId],
  );
  const allUploaded = data.upload_statuses.every((s) => s.has_uploaded);
  const pendingUploads = data.upload_statuses.filter((s) => !s.has_uploaded);
  const isFinalized = data.is_finalized === true;
  const unmappedCount = data.unmapped_categories.length;

  return (
    <CardShell
      label="Imported"
      info={
        <ImportedInfo
          buckets={[
            ["Household", buckets.household],
            ["Personal (you)", buckets.personal],
            ["Spotted", buckets.spotted],
            ["Partner-paid", buckets.partnerPaid],
            ["Settlement", buckets.settlement],
            ["Excluded", buckets.excluded],
          ]}
          periodLabel={periodLabel}
        />
      }
    >
      <p className="text-lg font-semibold tabular-nums text-foreground">
        {plural("transaction", buckets.total.count)} ·{" "}
        {formatCurrency(buckets.total.amount)} imported
      </p>
      <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[11px] leading-tight text-muted-foreground/70">
        {allUploaded ? (
          <UploadedPip label="Both uploaded" />
        ) : (
          <PendingPip label={plural("pending upload", pendingUploads.length)} />
        )}
        <span>·</span>
        <span>
          {isFinalized ? (
            <span className="inline-flex items-center gap-1">
              <Lock className="size-3" />
              Finalized
            </span>
          ) : (
            "Open"
          )}
        </span>
        {unmappedCount > 0 && (
          <>
            <span>·</span>
            <Link
              to="/settings"
              className="inline-flex items-center gap-1 text-warning underline underline-offset-2"
            >
              <AlertTriangle className="size-3" />
              {plural("unmapped", unmappedCount)}
            </Link>
          </>
        )}
      </p>
    </CardShell>
  );
}

function UploadedPip({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-foreground">
      <CheckCircle2 className="size-3 text-positive" />
      {label}
    </span>
  );
}

function PendingPip({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-warning">
      <AlertTriangle className="size-3" />
      {label}
    </span>
  );
}

interface InViewCardProps {
  data: ReconciliationResponse;
  filtered: TransactionResponse[];
  scope: TransactionScope;
  periodLabel: string;
}

function InViewCard({ data, filtered, scope, periodLabel }: InViewCardProps) {
  return (
    <CardShell label="In view" info={<InViewInfo periodLabel={periodLabel} />}>
      <p className="text-lg font-semibold tabular-nums text-foreground">
        {formatCurrency(sumNet(filtered.filter((tx) => !tx.is_settlement)))}
      </p>
      <p className="text-[11px] leading-tight text-muted-foreground/70">
        {filtered.length} of {data.transactions.length} · {SCOPE_LABELS[scope]}
      </p>
    </CardShell>
  );
}

function CardShell({
  label,
  info,
  children,
}: {
  label: string;
  info: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card className="flex flex-col gap-1 p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <InfoPopover label={`About ${label}`}>{info}</InfoPopover>
      </div>
      {children}
    </Card>
  );
}

function SettlementInfo({
  hasSettleUp,
  singleMonth,
}: {
  hasSettleUp: boolean;
  singleMonth: boolean;
}) {
  return (
    <>
      <p>
        <strong>Formula:</strong> gross balance from this period's split
        transactions — any split under 100%, household or personal — minus any
        linked settlement payments. Matches the Settle Up page exactly.
      </p>
      {!singleMonth && (
        <p>
          Showing a date range, not a single month — select one month to load
          Settle Up data.
        </p>
      )}
      {singleMonth && !hasSettleUp && (
        <p>
          Falling back to the reconciliation gross because no settlements have
          been linked yet for this month.
        </p>
      )}
      <p>
        Click the figure above to filter the table to the{" "}
        <HandCoins className="inline size-3 text-primary" /> settlement rows
        you've linked.
      </p>
    </>
  );
}

function ImportedInfo({
  buckets,
  periodLabel,
}: {
  buckets: Array<readonly [string, { count: number; amount: number }]>;
  periodLabel: string;
}) {
  const visible = buckets.filter(([, stat]) => stat.count > 0);
  return (
    <>
      <p>
        Total transactions and dollar throughput imported for {periodLabel}.
        Bucket totals use absolute values (a $50 expense and a $50 refund both
        contribute $50 of throughput).
      </p>
      <ul className="space-y-0.5">
        {visible.map(([label, stat]) => (
          <li
            key={label}
            className="flex items-baseline justify-between gap-2 tabular-nums"
          >
            <span className="text-muted-foreground">{label}</span>
            <span className="text-foreground">
              {formatCurrency(stat.amount)} · {plural("tx", stat.count)}
            </span>
          </li>
        ))}
      </ul>
      <p className="italic text-muted-foreground">
        <strong>Spotted</strong> only includes items <em>you</em> fronted.
        Partner-fronted items aren't in your dataset and require a backend
        change to surface.
      </p>
    </>
  );
}

function InViewInfo({ periodLabel }: { periodLabel: string }) {
  return (
    <p>
      Net total of every transaction matching the active filters. Refunds reduce
      the total; linked settlement transfers don't count (money movement, not
      spending). Filter-scoped — changes as you adjust filters within{" "}
      {periodLabel}.
    </p>
  );
}
