import { Check, Loader2 } from "lucide-react";
import type { ToolCall } from "@/lib/chat";

const TOOL_LABELS: Record<string, string> = {
  get_settlement_balance: "settlement",
  get_budget_overview: "budget",
  search_transactions: "transactions",
  get_spending_by_group: "spending",
  get_spending_trends: "trends",
  get_dashboard_status: "status",
};

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
      {isDone ? `Checked ${label}` : `Looking up ${label}…`}
    </span>
  );
}
