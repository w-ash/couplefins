import { Check, X } from "lucide-react";
import { ConfirmationCard } from "@/components/chat/ConfirmationCard";
import { ProgressBar } from "@/components/ProgressBar";
import type { ConfirmationState, ToolCall } from "@/lib/chat";
import { cn } from "@/lib/cn";
import { amountColorClass, formatCurrency, formatDate } from "@/lib/format";
import { getHealthStyle } from "@/lib/health-styles";
import { heroCardClass, tableHeaderRowClass } from "@/lib/layout";

// --- Result type interfaces (mirror Python tool executor output) ---

interface SettlementResult {
  // "all_months" for the total-outstanding answer; absent for a month query.
  scope?: string;
  // Month label ("2026-03") or the outstanding span ("2026-03 to 2026-05").
  month?: string;
  is_finalized?: boolean;
  remaining_balance: number;
  from?: string;
  to?: string;
  gross_amount?: number;
  net_from?: string;
  net_to?: string;
  status?: string;
  uploads?: { person: string; uploaded: boolean }[];
}

interface BudgetGroup {
  name: string;
  spent: number;
  budget: number | null;
  health: string | null;
}

interface BudgetResult {
  month: string;
  scope: string;
  groups: BudgetGroup[];
  total_spent: number;
  total_budget: number;
  over_budget: string[];
}

interface TransactionRow {
  date: string;
  merchant: string;
  amount: number;
  category: string;
  payer: string;
  split: string;
  household: boolean;
}

interface SearchResult {
  total_count: number;
  showing: number;
  transactions: TransactionRow[];
}

interface SpendingByGroupResult {
  month: string;
  groups: { name: string; spent: number }[];
  total: number;
}

interface SpendingTrendsResult {
  year: number;
  groups: { name: string }[];
}

interface DashboardStatusResult {
  month: string;
  uploads: { person: string; uploaded: boolean; count: number }[];
  is_finalized: boolean;
  transaction_count: number;
  finalization_warnings: string[];
}

// --- Card variants ---

function SettlementCard({ result }: { result: SettlementResult }) {
  // The net direction is authoritative — payments can reverse who owes whom.
  // A missing net direction with a gross balance means the month is settled.
  const settled = result.from && !result.net_from;
  const grossDiffers =
    result.remaining_balance !== result.gross_amount ||
    result.net_from !== result.from;
  const grossContext = result.from &&
    result.to &&
    result.gross_amount != null &&
    grossDiffers && (
      <p className="text-xs text-muted-foreground">
        {result.from} owed {result.to}{" "}
        <span className="tabular-nums">
          {formatCurrency(result.gross_amount)}
        </span>{" "}
        before payments
      </p>
    );
  // The all-months answer carries the outstanding span as its month label.
  const heading =
    result.scope === "all_months"
      ? `Total outstanding${result.month ? ` · ${result.month}` : ""}`
      : `${result.month} settlement`;

  return (
    <div className={cn(heroCardClass, "px-4 py-3")}>
      {result.net_from && result.net_to ? (
        <>
          <p className="text-xs text-muted-foreground">{heading}</p>
          <p className="text-base font-medium">
            {result.net_from} owes {result.net_to}{" "}
            <span className="tabular-nums">
              {formatCurrency(result.remaining_balance)}
            </span>
          </p>
          {grossContext}
        </>
      ) : settled ? (
        <>
          <p className="text-xs text-muted-foreground">{heading}</p>
          <p className="text-base font-medium">All settled</p>
          {grossContext}
        </>
      ) : (
        <p className="text-sm text-muted-foreground">{result.status}</p>
      )}
    </div>
  );
}

function BudgetCard({ result }: { result: BudgetResult }) {
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        {result.month} {result.scope} budget
      </p>
      {result.groups.map((g) => {
        const pct =
          g.budget != null && g.budget > 0
            ? Math.min((g.spent / g.budget) * 100, 100)
            : 0;
        const style = getHealthStyle(g.health);
        return (
          <div key={g.name} className="space-y-0.5">
            <div className="flex justify-between text-xs">
              <span>{g.name}</span>
              <span className="tabular-nums text-muted-foreground">
                {formatCurrency(g.spent)}
                {g.budget != null ? ` / ${formatCurrency(g.budget)}` : ""}
              </span>
            </div>
            {g.budget != null && (
              <ProgressBar pct={pct} barColor={style.barColor} />
            )}
          </div>
        );
      })}
      <div className="flex justify-between border-t border-border pt-1.5 text-xs font-medium">
        <span>Total</span>
        <span className="tabular-nums">
          {formatCurrency(result.total_spent)}
          {result.total_budget > 0
            ? ` / ${formatCurrency(result.total_budget)}`
            : ""}
        </span>
      </div>
    </div>
  );
}

function TransactionTableCard({ result }: { result: SearchResult }) {
  return (
    <div>
      <table className="w-full text-xs">
        <thead>
          <tr className={tableHeaderRowClass}>
            <th className="py-1 pr-2 font-medium">Date</th>
            <th className="py-1 pr-2 font-medium">Merchant</th>
            <th className="py-1 pr-2 text-right font-medium">Amount</th>
            <th className="py-1 font-medium">Category</th>
          </tr>
        </thead>
        <tbody>
          {result.transactions.map((tx) => (
            <tr
              key={`${tx.date}-${tx.merchant}-${tx.amount}`}
              className="border-b border-border/50"
            >
              <td className="py-1 pr-2 text-muted-foreground">
                {formatDate(tx.date)}
              </td>
              <td className="py-1 pr-2">{tx.merchant}</td>
              <td
                className={cn(
                  "py-1 pr-2 text-right tabular-nums",
                  amountColorClass(tx.amount),
                )}
              >
                {formatCurrency(tx.amount)}
              </td>
              <td className="py-1 text-muted-foreground">{tx.category}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {result.total_count > result.showing && (
        <p className="mt-1 text-xs text-muted-foreground">
          Showing {result.showing} of {result.total_count} transactions
        </p>
      )}
    </div>
  );
}

function SpendingByGroupCard({ result }: { result: SpendingByGroupResult }) {
  return (
    <div>
      <p className="mb-1 text-xs text-muted-foreground">
        {result.month} spending by group
      </p>
      <table className="w-full text-xs">
        <thead>
          <tr className={tableHeaderRowClass}>
            <th className="py-1 pr-2 font-medium">Group</th>
            <th className="py-1 text-right font-medium">Spent</th>
          </tr>
        </thead>
        <tbody>
          {result.groups.map((g) => (
            <tr key={g.name} className="border-b border-border/50">
              <td className="py-1 pr-2">{g.name}</td>
              <td className="py-1 text-right tabular-nums">
                {formatCurrency(g.spent)}
              </td>
            </tr>
          ))}
          <tr className="font-medium">
            <td className="py-1 pr-2">Total</td>
            <td className="py-1 text-right tabular-nums">
              {formatCurrency(result.total)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function SpendingTrendsCard({ result }: { result: SpendingTrendsResult }) {
  return (
    <p className="text-xs text-muted-foreground">
      {result.year} trends across {result.groups.length} category groups
    </p>
  );
}

function DashboardStatusCard({ result }: { result: DashboardStatusResult }) {
  return (
    <div className="space-y-1.5 text-xs">
      <p className="text-muted-foreground">{result.month} status</p>
      {result.uploads.map((u) => (
        <div key={u.person} className="flex items-center gap-1.5">
          {u.uploaded ? (
            <Check className="size-3 text-positive" />
          ) : (
            <X className="size-3 text-negative" />
          )}
          <span>
            {u.person}:{" "}
            {u.uploaded ? `${u.count} transactions` : "not uploaded"}
          </span>
        </div>
      ))}
      <p>
        {result.transaction_count} total transactions
        {result.is_finalized ? " (finalized)" : ""}
      </p>
      {result.finalization_warnings.length > 0 && (
        <div className="space-y-0.5 text-warning-muted-foreground">
          {result.finalization_warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Generic renderer (default for tools without a bespoke card) ---

function formatGenericValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => `${formatGenericKey(k)}: ${formatGenericValue(v)}`)
      .join(" · ");
  }
  return String(value);
}

function formatGenericKey(key: string): string {
  return key.replaceAll("_", " ");
}

function GenericListTable({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = Object.keys(rows[0]);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className={tableHeaderRowClass}>
            {columns.map((col) => (
              <th key={col} className="py-1 pr-2 text-left font-medium">
                {formatGenericKey(col)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: rows are static render-once data
            <tr key={i} className="border-b border-border/50">
              {columns.map((col) => (
                <td key={col} className="py-1 pr-2">
                  {formatGenericValue(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function GenericToolResultCard({
  result,
}: {
  result: Record<string, unknown>;
}) {
  const entries = Object.entries(result);
  if (entries.length === 0) return null;
  const scalars = entries.filter(([, v]) => !Array.isArray(v));
  const lists = entries.filter((entry): entry is [string, unknown[]] =>
    Array.isArray(entry[1]),
  );

  return (
    <div className="space-y-2 text-xs">
      {scalars.length > 0 && (
        <div className="space-y-0.5">
          {scalars.map(([key, value]) => (
            <div key={key} className="flex justify-between gap-4">
              <span className="text-muted-foreground">
                {formatGenericKey(key)}
              </span>
              <span className="text-right tabular-nums">
                {formatGenericValue(value)}
              </span>
            </div>
          ))}
        </div>
      )}
      {lists.map(([key, items]) => (
        <div key={key} className="space-y-0.5">
          <p className="font-medium text-muted-foreground">
            {formatGenericKey(key)}
          </p>
          {items.length === 0 ? (
            <p className="text-muted-foreground">none</p>
          ) : typeof items[0] === "object" && items[0] !== null ? (
            <GenericListTable rows={items as Record<string, unknown>[]} />
          ) : (
            <p>{items.map(formatGenericValue).join(", ")}</p>
          )}
        </div>
      ))}
    </div>
  );
}

// --- Pending confirmation detection ---

interface PendingConfirmationResult {
  status: "pending_confirmation";
  action_id: string;
  description: string;
  details: Record<string, unknown>;
}

function isPendingConfirmation(
  result: unknown,
): result is PendingConfirmationResult {
  if (!result || typeof result !== "object") return false;
  return (result as Record<string, unknown>).status === "pending_confirmation";
}

// --- Main dispatcher ---

export function ToolResultCard({
  toolCall,
  confirmationState,
  onConfirm,
  onCancel,
}: {
  toolCall: ToolCall;
  confirmationState?: ConfirmationState;
  onConfirm?: (actionId: string) => void;
  onCancel?: (actionId: string) => void;
}) {
  if (toolCall.result === undefined || toolCall.isError) return null;
  const result = toolCall.result;

  // Mutation tools return pending_confirmation → render ConfirmationCard
  if (isPendingConfirmation(result) && onConfirm && onCancel) {
    return (
      <ConfirmationCard
        actionId={result.action_id}
        description={result.description}
        details={result.details}
        toolName={toolCall.name}
        state={confirmationState ?? "pending"}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />
    );
  }

  switch (toolCall.name) {
    case "get_settlement_balance":
      return <SettlementCard result={result as SettlementResult} />;
    case "get_budget_overview":
      return <BudgetCard result={result as BudgetResult} />;
    case "search_transactions":
      return <TransactionTableCard result={result as SearchResult} />;
    case "get_spending_by_group":
      return <SpendingByGroupCard result={result as SpendingByGroupResult} />;
    case "get_spending_trends":
      return <SpendingTrendsCard result={result as SpendingTrendsResult} />;
    case "get_dashboard_status":
      return <DashboardStatusCard result={result as DashboardStatusResult} />;
    default:
      // Every other tool renders through the generic key/value card.
      if (result && typeof result === "object" && !Array.isArray(result)) {
        return (
          <GenericToolResultCard result={result as Record<string, unknown>} />
        );
      }
      return null;
  }
}
