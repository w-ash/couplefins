import { Check, Loader2 } from "lucide-react";
import type { ToolCall } from "@/lib/chat";

const TOOL_LABELS: Record<string, string> = {
  get_settlement_balance: "settlement",
  get_budget_overview: "budget",
  search_transactions: "transactions",
  get_spending_by_group: "spending",
  get_spending_trends: "trends",
  get_dashboard_status: "status",
  update_budget: "budget update",
  update_transaction_split: "split update",
  bulk_update_transactions: "bulk update",
};

const MUTATION_TOOLS = new Set([
  "update_budget",
  "update_transaction_split",
  "bulk_update_transactions",
]);

export function ToolCallIndicator({ toolCall }: { toolCall: ToolCall }) {
  const label = TOOL_LABELS[toolCall.name] ?? toolCall.name;
  const isDone = toolCall.result !== undefined;

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
      {isDone ? (
        <Check className="size-3" />
      ) : (
        <Loader2 className="size-3 animate-spin" />
      )}
      {isDone
        ? `Checked ${label}`
        : MUTATION_TOOLS.has(toolCall.name)
          ? `Proposing ${label}…`
          : `Looking up ${label}…`}
    </span>
  );
}
