import { Check, Copy } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { useGetCategoryGroups } from "@/api/generated/category-groups/category-groups";
import type {
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
  formatSignedCurrency,
  isZeroCurrency,
  plural,
} from "@/lib/format";
import { tableHeaderRowClass } from "@/lib/layout";
import {
  type TransactionScope,
  TX_FILTER_PARAMS,
} from "@/lib/transaction-filters";

interface Props {
  data: SettleUpDataResponse;
  personNames: Map<string, string>;
}

type ViewMode = "by-payer" | "by-category";

const VIEW_OPTIONS = [
  { value: "by-payer" as const, label: "By payer" },
  { value: "by-category" as const, label: "By category" },
];

// Settlement entries set amount/txns/shares to null — they render as a "—"
// dash and only contribute to the Net column.
interface LedgerRow {
  key: string;
  activity: string;
  href: string;
  amount: number | null;
  txns: number | null;
  p0Share: number | null;
  p1Share: number | null;
  net: number;
}

interface LedgerRows {
  splits: LedgerRow[];
  settlements: LedgerRow[];
}

const EMPTY_ROWS: LedgerRows = { splits: [], settlements: [] };

const DASH = <span className="text-muted-foreground/40">—</span>;

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

  const rows = useMemo(
    () =>
      p0
        ? buildLedgerRows({
            data,
            view,
            p0Id: p0.id,
            personNames,
            groupCategories,
          })
        : EMPTY_ROWS,
    [data, view, p0, personNames, groupCategories],
  );

  const totals = useMemo(() => computeTotals(rows), [rows]);

  const handleCopy = useCallback(async () => {
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
      money(totals.amount),
      int(totals.txns),
      money(totals.p0Share),
      money(totals.p1Share),
      money(totals.net),
    ];
    const allRows = [...rows.splits, ...rows.settlements];
    const tsv = buildTsv(headers, allRows, totalRow);
    const html = buildHtml(headers, allRows, totalRow);
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
  }, [rows, totals, p0Name, p1Name]);

  if (!p0 || !p1 || (!hasSplits && !hasSettlements)) return null;

  const p0Split = data.payer_splits.find(
    (s) => s.payer_person_id === p0.id && s.transaction_count > 0,
  );
  const p1Split = data.payer_splits.find(
    (s) => s.payer_person_id === p1.id && s.transaction_count > 0,
  );

  const narrative = buildBalanceNarrative({
    p0: { id: p0.id, name: p0Name, split: p0Split },
    p1: { id: p1.id, name: p1Name, split: p1Split },
    settlements: data.recorded_settlements,
    totalNet: totals.net,
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
                {rows.splits.length > 0 ? (
                  rows.splits.map((r) => <LedgerRowTr key={r.key} row={r} />)
                ) : (
                  <EmptyRow message="No split bills for this period yet." />
                )}
                {rows.settlements.map((r) => (
                  <LedgerRowTr key={r.key} row={r} />
                ))}
                <TotalRow
                  totalAmount={totals.amount}
                  totalTxns={totals.txns}
                  p0Share={totals.p0Share}
                  p1Share={totals.p1Share}
                  totalNet={totals.net}
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

interface AuditTotals {
  amount: number;
  txns: number;
  p0Share: number;
  p1Share: number;
  net: number;
}

// Totals sum the rendered rows, so the Total line always ties to the table
// body — in either view, and including settlement rows' Net contributions.
function computeTotals(rows: LedgerRows): AuditTotals {
  const totals: AuditTotals = {
    amount: 0,
    txns: 0,
    p0Share: 0,
    p1Share: 0,
    net: 0,
  };
  for (const r of [...rows.splits, ...rows.settlements]) {
    totals.amount += r.amount ?? 0;
    totals.txns += r.txns ?? 0;
    totals.p0Share += r.p0Share ?? 0;
    totals.p1Share += r.p1Share ?? 0;
    totals.net += r.net;
  }
  return totals;
}

function LedgerRowTr({ row }: { row: LedgerRow }) {
  return (
    <tr className="border-b border-border-muted">
      <td className="py-2 pr-4">
        <Link
          to={row.href}
          className="text-foreground underline-offset-2 hover:underline focus-visible:underline focus-visible:outline-none"
        >
          {row.activity}
        </Link>
      </td>
      <td className="py-2 pr-4 text-right tabular-nums">
        {row.amount == null ? DASH : formatCurrency(row.amount)}
      </td>
      <td className="py-2 pr-4 text-right tabular-nums">
        {row.txns == null ? DASH : row.txns}
      </td>
      <td className="py-2 pr-4 text-right tabular-nums">
        {row.p0Share == null ? DASH : formatCurrency(row.p0Share)}
      </td>
      <td className="py-2 pr-4 text-right tabular-nums">
        {row.p1Share == null ? DASH : formatCurrency(row.p1Share)}
      </td>
      <td className="py-2 text-right tabular-nums">
        {formatSignedCurrency(row.net)}
      </td>
    </tr>
  );
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
  const settled = isZeroCurrency(totalNet);
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

function buildLedgerRows({
  data,
  view,
  p0Id,
  personNames,
  groupCategories,
}: {
  data: SettleUpDataResponse;
  view: ViewMode;
  p0Id: string;
  personNames: Map<string, string>;
  groupCategories: Map<string, string[]>;
}): LedgerRows {
  const splits: LedgerRow[] = [];

  if (view === "by-category") {
    for (const r of data.payer_group_splits) {
      const payerName = personNames.get(r.payer_person_id) ?? "Unknown";
      const cats = r.group_id ? (groupCategories.get(r.group_id) ?? []) : [];
      splits.push(
        splitRow(r, p0Id, {
          key: `${r.group_id ?? "uncat"}-${r.payer_person_id}`,
          activity: `${r.group_name} · ${payerName}`,
          href: buildTransactionsUrl({
            year: data.year,
            month: data.month,
            payerId: r.payer_person_id,
            categoryNames: cats,
            scope: "household",
          }),
        }),
      );
    }
  } else {
    for (const r of data.payer_splits) {
      if (r.transaction_count === 0) continue;
      const payerName = personNames.get(r.payer_person_id) ?? "Unknown";
      splits.push(
        splitRow(r, p0Id, {
          key: `payer-${r.payer_person_id}`,
          activity: `${payerName}'s bills`,
          href: buildTransactionsUrl({
            year: data.year,
            month: data.month,
            payerId: r.payer_person_id,
            scope: "household",
          }),
        }),
      );
    }
  }

  const settlements = data.recorded_settlements.map((s) =>
    settlementRow(s, p0Id, personNames),
  );

  return { splits, settlements };
}

// PayerGroupSplitSummaryResponse is structurally a superset of
// PayerSplitSummaryResponse — both views share the same row shape.
function splitRow(
  r: PayerSplitSummaryResponse,
  p0Id: string,
  parts: { key: string; activity: string; href: string },
): LedgerRow {
  const isP0 = r.payer_person_id === p0Id;
  return {
    ...parts,
    amount: r.fronted,
    txns: r.transaction_count,
    p0Share: isP0 ? r.their_share : r.partner_share,
    p1Share: isP0 ? r.partner_share : r.their_share,
    net: isP0 ? r.partner_share : -r.partner_share,
  };
}

function settlementRow(
  s: SettlementResponse,
  p0Id: string,
  personNames: Map<string, string>,
): LedgerRow {
  const fromName = personNames.get(s.from_person_id) ?? "Unknown";
  const toName = personNames.get(s.to_person_id) ?? "Unknown";
  const settledAt = new Date(s.settled_at);
  const settledDate = formatShortDate(s.settled_at);
  const activity = s.is_waived
    ? `${settledDate} · Balance waived`
    : `${settledDate} · ${fromName} → ${toName}${s.method ? ` via ${s.method}` : ""}`;
  return {
    key: `settlement-${s.id}`,
    activity,
    href: buildTransactionsUrl({
      year: settledAt.getFullYear(),
      month: settledAt.getMonth() + 1,
      settlement: true,
    }),
    amount: null,
    txns: null,
    p0Share: null,
    p1Share: null,
    net: s.from_person_id === p0Id ? s.amount : -s.amount,
  };
}

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
  if (scope && scope !== "all") params.set(TX_FILTER_PARAMS.scope, scope);
  if (payerId) params.append(TX_FILTER_PARAMS.payer, payerId);
  for (const cat of categoryNames ?? [])
    params.append(TX_FILTER_PARAMS.category, cat);
  if (settlement) params.set(TX_FILTER_PARAMS.settlement, "1");
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

function rowToClipboard(row: LedgerRow): ClipboardRow {
  return [
    row.activity,
    row.amount == null ? null : money(row.amount),
    row.txns == null ? null : int(row.txns),
    row.p0Share == null ? null : money(row.p0Share),
    row.p1Share == null ? null : money(row.p1Share),
    money(row.net),
  ];
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
  rows: LedgerRow[],
  totalRow: ClipboardRow,
): string {
  const allRows = [headers, ...rows.map(rowToClipboard), totalRow];
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
  rows: LedgerRow[],
  totalRow: ClipboardRow,
): string {
  const headerCells = headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("");
  const bodyRows = rows
    .map(
      (row) =>
        `<tr>${rowToClipboard(row)
          .map((c) => `<td>${htmlCell(c)}</td>`)
          .join("")}</tr>`,
    )
    .join("");
  const totalCells = totalRow
    .map((c) => `<td><b>${htmlCell(c)}</b></td>`)
    .join("");
  return `<table><thead><tr>${headerCells}</tr></thead><tbody>${bodyRows}<tr>${totalCells}</tr></tbody></table>`;
}
