import { Check, Copy } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { useGetCategoryGroups } from "@/api/generated/category-groups/category-groups";
import type {
  PayerGroupSplitSummaryResponse,
  PayerSplitSummaryResponse,
  SettlementResponse,
  SettleUpDataResponse,
} from "@/api/generated/model";
import { Card } from "@/components/Card";
import { ExpandChevron } from "@/components/ExpandChevron";
import { SectionHeader } from "@/components/SectionHeader";
import { SegmentedControl } from "@/components/SegmentedControl";
import { cn } from "@/lib/cn";
import {
  buildSettlementLabel,
  formatCurrency,
  formatShortDate,
  plural,
} from "@/lib/format";
import { tableHeaderRowClass } from "@/lib/layout";
import type { TransactionScope } from "@/lib/transaction-filters";

interface Props {
  data: SettleUpDataResponse;
  personNames: Map<string, string>;
}

type ViewMode = "by-payer" | "by-category";

const VIEW_OPTIONS = [
  { value: "by-payer" as const, label: "By payer" },
  { value: "by-category" as const, label: "By category" },
];

export function SettleUpAuditTable({ data, personNames }: Props) {
  const [view, setView] = useState<ViewMode>("by-payer");
  const [showLedger, setShowLedger] = useState(false);
  const [copied, setCopied] = useState(false);
  const copyTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current !== null) {
        window.clearTimeout(copyTimeoutRef.current);
      }
    };
  }, []);

  const { data: categoryGroupsResponse } = useGetCategoryGroups();
  const categoryGroupsList =
    categoryGroupsResponse?.status === 200 ? categoryGroupsResponse.data : [];
  const groupCategories = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const g of categoryGroupsList) {
      map.set(
        g.id,
        g.categories.map((c) => c.name),
      );
    }
    return map;
  }, [categoryGroupsList]);

  const hasSplits = data.payer_splits.some((p) => p.transaction_count > 0);
  const hasSettlements = data.recorded_settlements.length > 0;

  const p0 = data.persons[0] ?? null;
  const p1 = data.persons[1] ?? null;
  const p0Name = (p0 && personNames.get(p0.id)) ?? "Person 1";
  const p1Name = (p1 && personNames.get(p1.id)) ?? "Person 2";

  let totalAmount = 0;
  let p0Share = 0;
  let p1Share = 0;
  let totalTxns = 0;
  let totalNet = 0;
  let p0Split: PayerSplitSummaryResponse | undefined;
  let p1Split: PayerSplitSummaryResponse | undefined;

  if (p0) {
    for (const split of data.payer_splits) {
      if (split.transaction_count === 0) continue;
      totalAmount += split.fronted;
      totalTxns += split.transaction_count;
      const payerIsP0 = split.payer_person_id === p0.id;
      if (payerIsP0) {
        p0Split = split;
        p0Share += split.their_share;
        p1Share += split.partner_share;
        totalNet += split.partner_share;
      } else {
        p1Split = split;
        p1Share += split.their_share;
        p0Share += split.partner_share;
        totalNet -= split.partner_share;
      }
    }
    for (const s of data.recorded_settlements) {
      totalNet += s.from_person_id === p0.id ? s.amount : -s.amount;
    }
  }

  const handleCopy = useCallback(async () => {
    if (!p0) return;
    const rows = buildClipboardRows({
      data,
      view,
      p0Id: p0.id,
      personNames,
    });
    const headers = [
      "Activity",
      "Amount",
      "Txns",
      `${p0Name}'s share`,
      `${p1Name}'s share`,
      "Net",
    ];
    const totalRow: ClipboardRow = [
      "Total",
      money(totalAmount),
      int(totalTxns),
      money(p0Share),
      money(p1Share),
      money(totalNet),
    ];
    const tsv = buildTsv(headers, rows, totalRow);
    const html = buildHtml(headers, rows, totalRow);
    try {
      await navigator.clipboard.write([
        new ClipboardItem({
          "text/plain": new Blob([tsv], { type: "text/plain" }),
          "text/html": new Blob([html], { type: "text/html" }),
        }),
      ]);
    } catch {
      await navigator.clipboard.writeText(tsv);
    }
    setCopied(true);
    if (copyTimeoutRef.current !== null) {
      window.clearTimeout(copyTimeoutRef.current);
    }
    copyTimeoutRef.current = window.setTimeout(() => {
      setCopied(false);
      copyTimeoutRef.current = null;
    }, 1500);
  }, [
    data,
    view,
    p0,
    personNames,
    p0Name,
    p1Name,
    totalAmount,
    totalTxns,
    p0Share,
    p1Share,
    totalNet,
  ]);

  if (!p0 || !p1 || (!hasSplits && !hasSettlements)) return null;

  const narrative = buildBalanceNarrative({
    p0: { id: p0.id, name: p0Name, split: p0Split },
    p1: { id: p1.id, name: p1Name, split: p1Split },
    settlements: data.recorded_settlements,
    totalNet,
    personNames,
  });

  return (
    <Card>
      <SectionHeader title="Showing the work" />
      <p className="mb-4 text-sm leading-relaxed text-foreground">
        {narrative}
      </p>
      <button
        type="button"
        onClick={() => setShowLedger((v) => !v)}
        aria-expanded={showLedger}
        className="inline-flex items-center gap-1.5 rounded text-xs font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:underline"
      >
        <ExpandChevron expanded={showLedger} />
        {showLedger ? "Hide ledger" : "Show ledger"}
      </button>

      {showLedger && (
        <>
          <div className="mt-4 mb-3 flex flex-wrap items-center justify-end gap-2">
            <button
              type="button"
              onClick={handleCopy}
              title={copied ? "Copied" : "Copy table for spreadsheet"}
              aria-label={
                copied
                  ? "Table copied"
                  : "Copy table for paste into a spreadsheet"
              }
              className={cn(
                "inline-flex h-8 items-center gap-1.5 rounded-full border border-border px-3 text-xs text-muted-foreground transition-colors",
                "hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              {copied ? (
                <>
                  <Check className="size-3.5" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="size-3.5" />
                  Copy
                </>
              )}
            </button>
            <SegmentedControl<ViewMode>
              options={VIEW_OPTIONS}
              value={view}
              onChange={setView}
              shape="pill"
              size="sm"
            />
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-spacing-0 text-sm">
              <thead>
                <tr className={tableHeaderRowClass}>
                  <th className="pb-2 pr-4 font-medium whitespace-nowrap">
                    Activity
                  </th>
                  <th className="pb-2 pr-4 text-right font-medium whitespace-nowrap tabular-nums">
                    Amount
                  </th>
                  <th className="pb-2 pr-4 text-right font-medium whitespace-nowrap tabular-nums">
                    Txns
                  </th>
                  <th className="pb-2 pr-4 text-right font-medium whitespace-nowrap tabular-nums">
                    {p0Name}'s share
                  </th>
                  <th className="pb-2 pr-4 text-right font-medium whitespace-nowrap tabular-nums">
                    {p1Name}'s share
                  </th>
                  <th className="pb-2 text-right font-medium whitespace-nowrap tabular-nums">
                    Net
                  </th>
                </tr>
              </thead>
              <tbody>
                {hasSplits ? (
                  view === "by-category" ? (
                    <PayerGroupRows
                      rows={data.payer_group_splits}
                      personNames={personNames}
                      p0Id={p0.id}
                      year={data.year}
                      month={data.month}
                      groupCategories={groupCategories}
                    />
                  ) : (
                    <PayerRows
                      rows={data.payer_splits}
                      personNames={personNames}
                      p0Id={p0.id}
                      year={data.year}
                      month={data.month}
                    />
                  )
                ) : (
                  <EmptyRow message="No split bills for this period yet." />
                )}
                {data.recorded_settlements.map((s) => (
                  <SettlementLedgerRow
                    key={s.id}
                    settlement={s}
                    personNames={personNames}
                    p0Id={p0.id}
                  />
                ))}
                <TotalRow
                  totalAmount={totalAmount}
                  totalTxns={totalTxns}
                  p0Share={p0Share}
                  p1Share={p1Share}
                  totalNet={totalNet}
                />
              </tbody>
            </table>
          </div>

          <p className="mt-3 text-xs text-muted-foreground">
            + in Net favors {p0Name}; − favors {p1Name}.
          </p>
        </>
      )}
    </Card>
  );
}

function PayerRows({
  rows,
  personNames,
  p0Id,
  year,
  month,
}: {
  rows: PayerSplitSummaryResponse[];
  personNames: Map<string, string>;
  p0Id: string;
  year: number;
  month: number;
}) {
  return (
    <>
      {rows
        .filter((r) => r.transaction_count > 0)
        .map((r) => {
          const payerName = personNames.get(r.payer_person_id) ?? "Unknown";
          const isP0 = r.payer_person_id === p0Id;
          return (
            <LedgerRow
              key={r.payer_person_id}
              activity={`${payerName}'s bills`}
              href={buildTransactionsUrl({
                year,
                month,
                payerId: r.payer_person_id,
                scope: "household",
              })}
              amount={r.fronted}
              txns={r.transaction_count}
              p0Share={isP0 ? r.their_share : r.partner_share}
              p1Share={isP0 ? r.partner_share : r.their_share}
              net={isP0 ? r.partner_share : -r.partner_share}
            />
          );
        })}
    </>
  );
}

function PayerGroupRows({
  rows,
  personNames,
  p0Id,
  year,
  month,
  groupCategories,
}: {
  rows: PayerGroupSplitSummaryResponse[];
  personNames: Map<string, string>;
  p0Id: string;
  year: number;
  month: number;
  groupCategories: Map<string, string[]>;
}) {
  return (
    <>
      {rows.map((r) => {
        const payerName = personNames.get(r.payer_person_id) ?? "Unknown";
        const isP0 = r.payer_person_id === p0Id;
        const cats = r.group_id ? (groupCategories.get(r.group_id) ?? []) : [];
        return (
          <LedgerRow
            key={`${r.group_id ?? "uncat"}-${r.payer_person_id}`}
            activity={`${r.group_name} · ${payerName}`}
            href={buildTransactionsUrl({
              year,
              month,
              payerId: r.payer_person_id,
              categoryNames: cats,
              scope: "household",
            })}
            amount={r.fronted}
            txns={r.transaction_count}
            p0Share={isP0 ? r.their_share : r.partner_share}
            p1Share={isP0 ? r.partner_share : r.their_share}
            net={isP0 ? r.partner_share : -r.partner_share}
          />
        );
      })}
    </>
  );
}

function SettlementLedgerRow({
  settlement,
  personNames,
  p0Id,
}: {
  settlement: SettlementResponse;
  personNames: Map<string, string>;
  p0Id: string;
}) {
  const fromName = personNames.get(settlement.from_person_id) ?? "Unknown";
  const toName = personNames.get(settlement.to_person_id) ?? "Unknown";
  const settledAt = new Date(settlement.settled_at);
  const settledDate = formatShortDate(settlement.settled_at);
  const activity = settlement.is_waived
    ? `${settledDate} · Balance waived`
    : `${settledDate} · ${fromName} → ${toName}${settlement.method ? ` via ${settlement.method}` : ""}`;
  const senderIsP0 = settlement.from_person_id === p0Id;
  return (
    <LedgerRow
      activity={activity}
      href={buildTransactionsUrl({
        year: settledAt.getFullYear(),
        month: settledAt.getMonth() + 1,
        settlement: true,
      })}
      amount={null}
      txns={null}
      p0Share={null}
      p1Share={null}
      net={senderIsP0 ? settlement.amount : -settlement.amount}
    />
  );
}

function LedgerRow({
  activity,
  href,
  amount,
  txns,
  p0Share,
  p1Share,
  net,
}: {
  activity: string;
  href: string;
  amount: number | null;
  txns: number | null;
  p0Share: number | null;
  p1Share: number | null;
  net: number;
}) {
  return (
    <tr className="border-b border-border-muted">
      <td className="py-2 pr-4">
        <Link
          to={href}
          className="text-foreground underline-offset-2 hover:underline focus-visible:underline focus-visible:outline-none"
        >
          {activity}
        </Link>
      </td>
      <td className="py-2 pr-4 text-right tabular-nums">
        {amount == null ? <Dash /> : formatCurrency(amount)}
      </td>
      <td className="py-2 pr-4 text-right tabular-nums">
        {txns == null ? <Dash /> : txns}
      </td>
      <td className="py-2 pr-4 text-right tabular-nums">
        {p0Share == null ? <Dash /> : formatCurrency(p0Share)}
      </td>
      <td className="py-2 pr-4 text-right tabular-nums">
        {p1Share == null ? <Dash /> : formatCurrency(p1Share)}
      </td>
      <td className="py-2 text-right tabular-nums">
        {formatSignedCurrency(net)}
      </td>
    </tr>
  );
}

function Dash() {
  return <span className="text-muted-foreground/40">—</span>;
}

function EmptyRow({ message }: { message: string }) {
  return (
    <tr className="border-b border-border-muted">
      <td
        colSpan={6}
        className="py-3 text-center text-sm italic text-muted-foreground"
      >
        {message}
      </td>
    </tr>
  );
}

function TotalRow({
  totalAmount,
  totalTxns,
  p0Share,
  p1Share,
  totalNet,
}: {
  totalAmount: number;
  totalTxns: number;
  p0Share: number;
  p1Share: number;
  totalNet: number;
}) {
  return (
    <tr>
      <td className="pt-3 pr-4 font-medium text-foreground">Total</td>
      <td className="pt-3 pr-4 text-right font-medium tabular-nums">
        {formatCurrency(totalAmount)}
      </td>
      <td className="pt-3 pr-4 text-right font-medium tabular-nums">
        {totalTxns}
      </td>
      <td className="pt-3 pr-4 text-right font-medium tabular-nums">
        {formatCurrency(p0Share)}
      </td>
      <td className="pt-3 pr-4 text-right font-medium tabular-nums">
        {formatCurrency(p1Share)}
      </td>
      <td className="pt-3 text-right font-medium tabular-nums">
        {formatSignedCurrency(totalNet)}
      </td>
    </tr>
  );
}

function formatSignedCurrency(amount: number): string {
  if (Math.abs(amount) < 0.005) return formatCurrency(0);
  const sign = amount > 0 ? "+" : "−";
  return `${sign}${formatCurrency(Math.abs(amount))}`;
}

type Party = {
  id: string;
  name: string;
  split: PayerSplitSummaryResponse | undefined;
};

// Plain-English summary of how the balance was reached.
// Reaches the reader before the ledger does — the ledger is opt-in details.
function buildBalanceNarrative({
  p0,
  p1,
  settlements,
  totalNet,
  personNames,
}: {
  p0: Party;
  p1: Party;
  settlements: SettlementResponse[];
  totalNet: number;
  personNames: Map<string, string>;
}): string {
  const settled = Math.abs(totalNet) < 0.005;
  const result = buildSettlementLabel(
    settled
      ? null
      : {
          amount: Math.abs(totalNet),
          from_person_id: totalNet > 0 ? p1.id : p0.id,
          to_person_id: totalNet > 0 ? p0.id : p1.id,
        },
    personNames,
    { includeToName: true, settledLabel: "the balance is settled" },
  );

  const lead: string[] = [];
  for (const { name, split } of [p0, p1]) {
    if (split) {
      lead.push(
        `${name} fronted ${formatCurrency(split.fronted)} across ${plural("bill", split.transaction_count)}`,
      );
    }
  }

  const settlementClause = describeSettlements(settlements);
  const action = [lead.length > 0 ? "splitting" : "", settlementClause]
    .filter(Boolean)
    .join(" and ");
  const afterClause = action ? `After ${action}, ${result}` : result;

  return [lead.join("; "), afterClause].filter(Boolean).join(". ") + ".";
}

function describeSettlements(settlements: SettlementResponse[]): string {
  const [first, ...rest] = settlements;
  if (!first) return "";
  if (rest.length > 0) return `${settlements.length} settlements`;
  if (first.is_waived) return "a waiver";
  const date = formatShortDate(first.settled_at);
  if (first.method) return `one ${first.method} transfer on ${date}`;
  return `one transfer on ${date}`;
}

// Constructs a Transactions page URL using existing URL params:
//   year, month — date range for the period
//   payer (multi) — filter by payer person id
//   cat (multi) — filter by category name (use to drill into a category-group)
//   scope — household / personal / spotted / all
//   settlement=1 — filter to settlement-linked transactions
function buildTransactionsUrl({
  year,
  month,
  payerId,
  categoryNames,
  settlement,
  scope,
}: {
  year: number;
  month: number;
  payerId?: string;
  categoryNames?: string[];
  settlement?: boolean;
  scope?: TransactionScope;
}): string {
  const params = new URLSearchParams();
  params.set("year", String(year));
  params.set("month", String(month));
  if (scope && scope !== "all") params.set("scope", scope);
  if (payerId) params.append("payer", payerId);
  for (const cat of categoryNames ?? []) params.append("cat", cat);
  if (settlement) params.set("settlement", "1");
  return `/transactions?${params.toString()}`;
}

type ClipboardCell =
  | string
  | null
  | { kind: "money"; value: number }
  | { kind: "int"; value: number };
type ClipboardRow = ClipboardCell[];

const money = (value: number): ClipboardCell => ({ kind: "money", value });
const int = (value: number): ClipboardCell => ({ kind: "int", value });

function buildClipboardRows({
  data,
  view,
  p0Id,
  personNames,
}: {
  data: SettleUpDataResponse;
  view: ViewMode;
  p0Id: string;
  personNames: Map<string, string>;
}): ClipboardRow[] {
  const rows: ClipboardRow[] = [];

  if (view === "by-category") {
    for (const r of data.payer_group_splits) {
      const isP0 = r.payer_person_id === p0Id;
      const payerName = personNames.get(r.payer_person_id) ?? "Unknown";
      rows.push([
        `${r.group_name} · ${payerName}`,
        money(r.fronted),
        int(r.transaction_count),
        money(isP0 ? r.their_share : r.partner_share),
        money(isP0 ? r.partner_share : r.their_share),
        money(isP0 ? r.partner_share : -r.partner_share),
      ]);
    }
  } else {
    for (const r of data.payer_splits) {
      if (r.transaction_count === 0) continue;
      const isP0 = r.payer_person_id === p0Id;
      const payerName = personNames.get(r.payer_person_id) ?? "Unknown";
      rows.push([
        `${payerName}'s bills`,
        money(r.fronted),
        int(r.transaction_count),
        money(isP0 ? r.their_share : r.partner_share),
        money(isP0 ? r.partner_share : r.their_share),
        money(isP0 ? r.partner_share : -r.partner_share),
      ]);
    }
  }

  for (const s of data.recorded_settlements) {
    const fromName = personNames.get(s.from_person_id) ?? "Unknown";
    const toName = personNames.get(s.to_person_id) ?? "Unknown";
    const settledDate = formatShortDate(s.settled_at);
    const activity = s.is_waived
      ? `${settledDate} · Balance waived`
      : `${settledDate} · ${fromName} → ${toName}${s.method ? ` via ${s.method}` : ""}`;
    rows.push([
      activity,
      null,
      null,
      null,
      null,
      money(s.from_person_id === p0Id ? s.amount : -s.amount),
    ]);
  }

  return rows;
}

// Spreadsheet-friendly: money cells as raw decimals (no $ or commas) so Sheets
// parses them as numeric. Counts as integers. Empty string for null cells.
function tsvCell(cell: ClipboardCell): string {
  if (cell == null) return "";
  if (typeof cell === "string") return cell;
  if (cell.kind === "money") return cell.value.toFixed(2);
  return String(cell.value);
}

function buildTsv(
  headers: string[],
  rows: ClipboardRow[],
  totalRow: ClipboardRow,
): string {
  const allRows = [headers, ...rows, totalRow];
  return allRows.map((row) => row.map(tsvCell).join("\t")).join("\n");
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function htmlCell(cell: ClipboardCell): string {
  if (cell == null) return "";
  if (typeof cell === "string") return escapeHtml(cell);
  if (cell.kind === "money") return cell.value.toFixed(2);
  return String(cell.value);
}

function buildHtml(
  headers: string[],
  rows: ClipboardRow[],
  totalRow: ClipboardRow,
): string {
  const headerCells = headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("");
  const bodyRows = rows
    .map(
      (row) => `<tr>${row.map((c) => `<td>${htmlCell(c)}</td>`).join("")}</tr>`,
    )
    .join("");
  const totalCells = totalRow
    .map((c) => `<td><b>${htmlCell(c)}</b></td>`)
    .join("");
  return `<table><thead><tr>${headerCells}</tr></thead><tbody>${bodyRows}<tr>${totalCells}</tr></tbody></table>`;
}
