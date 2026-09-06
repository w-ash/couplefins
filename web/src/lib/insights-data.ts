import type {
  MonthlyGroupSpendingItem,
  SpendingTrendsResponse,
} from "@/api/generated/model";
import { MONTHS, SHORT_MONTHS } from "@/lib/format";
import type { InsightsPeriod } from "@/lib/insights-filters";
import {
  type FlowContext,
  groupColor,
  groupKey,
  UNCATEGORIZED_COLOR,
} from "@/lib/spending-flow";
import type { TransactionsLink } from "@/lib/transaction-links";

// ─── Period helpers ───

function sumMonths(
  items: MonthlyGroupSpendingItem[],
  predicate: (month: number) => boolean,
): number {
  return items
    .filter((i) => predicate(i.month))
    .reduce((s, i) => s + i.amount, 0);
}

/** "March 2026" or "Jan–Mar 2026". */
export function periodLabel(
  year: number,
  month: number,
  period: InsightsPeriod,
): string {
  if (period === "month") return `${MONTHS[month - 1]} ${year}`;
  if (month === 1) return `${MONTHS[0]} ${year}`;
  return `${SHORT_MONTHS[0]}–${SHORT_MONTHS[month - 1]} ${year}`;
}

// ─── Headline ───

export interface Headline {
  label: string;
  total: number;
  /** Spoken comparison to the previous period, when one exists. */
  comparison: { text: string; deltaPct: number; deltaAmount: number } | null;
}

function comparisonSentence(
  total: number,
  previous: number,
  than: string,
): Headline["comparison"] {
  if (previous <= 0) return null;
  const delta = total - previous;
  const direction = delta >= 0 ? "more" : "less";
  return {
    text: `${direction} than ${than}`,
    deltaPct: (delta / previous) * 100,
    deltaAmount: delta,
  };
}

export function buildHeadline(
  data: SpendingTrendsResponse,
  period: InsightsPeriod,
): Headline {
  const { year, month } = data;
  const total =
    period === "month"
      ? (data.monthly_totals.find((t) => t.month === month)?.total_amount ?? 0)
      : data.group_summaries.reduce((s, g) => s + g.ytd_total, 0);

  let comparison: Headline["comparison"];
  if (period === "month") {
    // January compares with last December; year to date with the same span
    // of the prior year.
    const previous =
      month > 1
        ? (data.monthly_totals.find((t) => t.month === month - 1)
            ?.total_amount ?? 0)
        : sumMonths(data.comparison_monthly_group_spending, (m) => m === 12);
    const previousLabel =
      month > 1 ? MONTHS[month - 2] : `${MONTHS[11]} ${year - 1}`;
    comparison = comparisonSentence(total, previous, previousLabel ?? "");
  } else {
    comparison = comparisonSentence(
      total,
      sumMonths(data.comparison_monthly_group_spending, (m) => m <= month),
      periodLabel(year - 1, month, "ytd"),
    );
  }

  return { label: periodLabel(year, month, period), total, comparison };
}

// ─── Monthly stack ───

export interface StackSeries {
  key: string;
  name: string;
  color: string;
}

export interface StackRow {
  month: number;
  label: string;
  total: number;
  priorYearTotal: number | null;
  /** Amount per group key; recharts reads these by `dataKey`. */
  [groupKey: string]: number | string | null;
}

export interface MonthlyStack {
  series: StackSeries[];
  rows: StackRow[];
}

/** Twelve rows, one column per group (year-to-date order), plus the prior
 * year's monthly total for the overlay line. */
export function buildMonthlyStack(
  data: SpendingTrendsResponse,
  ctx: FlowContext,
): MonthlyStack {
  const order = new Map<string, StackSeries>();
  for (const g of data.group_summaries)
    order.set(groupKey(g.group_id), {
      key: groupKey(g.group_id),
      name: g.group_name,
      color: groupColor(ctx, g.group_id),
    });
  for (const item of data.monthly_group_spending) {
    const key = groupKey(item.group_id);
    if (!order.has(key))
      order.set(key, {
        key,
        name: item.group_name,
        color: item.group_id
          ? groupColor(ctx, item.group_id)
          : UNCATEGORIZED_COLOR,
      });
  }
  const series = [...order.values()];
  const hasPrior = data.comparison_monthly_group_spending.length > 0;

  const rows: StackRow[] = Array.from({ length: 12 }, (_, i) => {
    const month = i + 1;
    const row: StackRow = {
      month,
      label: SHORT_MONTHS[i] ?? "",
      total: 0,
      priorYearTotal: hasPrior
        ? sumMonths(data.comparison_monthly_group_spending, (m) => m === month)
        : null,
    };
    for (const s of series) row[s.key] = 0;
    for (const item of data.monthly_group_spending) {
      if (item.month !== month) continue;
      const key = groupKey(item.group_id);
      // Refund-heavy months would draw below the axis; clamp the segment
      // and keep the true net in `total` for the tooltip.
      row[key] = Math.max(0, item.amount);
      row.total += item.amount;
    }
    return row;
  });
  return { series, rows };
}

// ─── Group rows ───

export interface TrendPoint {
  month: number;
  amount: number;
}

export interface GroupCategoryRow {
  name: string;
  amount: number;
  transactionCount: number;
  link: TransactionsLink;
}

export interface GroupRow {
  key: string;
  name: string;
  color: string;
  trend: TrendPoint[];
  priorTrend: TrendPoint[] | null;
  amount: number;
  share: number;
  /** vs the 3-month average (month) or the prior year to date (ytd). */
  delta: { pct: number; isNew: boolean; label: string } | null;
  transactionCount: number;
  categories: GroupCategoryRow[];
  link: TransactionsLink;
}

function trendFor(
  items: MonthlyGroupSpendingItem[],
  key: string,
): TrendPoint[] {
  return Array.from({ length: 12 }, (_, i) => ({
    month: i + 1,
    amount: items
      .filter((x) => x.month === i + 1 && groupKey(x.group_id) === key)
      .reduce((s, x) => s + x.amount, 0),
  }));
}

export function buildGroupRows(
  data: SpendingTrendsResponse,
  period: InsightsPeriod,
  ctx: FlowContext,
): GroupRow[] {
  const { month } = data;
  const cells =
    period === "month" ? data.month_flow.cells : data.ytd_flow.cells;
  const total = cells.reduce((s, c) => s + c.amount, 0);
  const hasPrior = data.comparison_monthly_group_spending.length > 0;

  const groups = new Map<
    string,
    {
      name: string;
      amount: number;
      count: number;
      cats: Map<string, GroupCategoryRow>;
    }
  >();
  for (const cell of cells) {
    const key = groupKey(cell.group_id);
    let entry = groups.get(key);
    if (!entry) {
      entry = { name: cell.group_name, amount: 0, count: 0, cats: new Map() };
      groups.set(key, entry);
    }
    entry.amount += cell.amount;
    entry.count += cell.transaction_count;
    const cat = entry.cats.get(cell.category);
    if (cat) {
      cat.amount += cell.amount;
      cat.transactionCount += cell.transaction_count;
    } else {
      entry.cats.set(cell.category, {
        name: cell.category,
        amount: cell.amount,
        transactionCount: cell.transaction_count,
        link: {
          range: ctx.range,
          scope: ctx.scope,
          categoryNames: [cell.category],
        },
      });
    }
  }

  const cards = new Map(
    data.comparison_cards.map((c) => [groupKey(c.group_id), c] as const),
  );

  return [...groups.entries()]
    .sort((a, b) => b[1].amount - a[1].amount)
    .map(([key, g]) => {
      const groupId = key === "uncategorized" ? null : key;
      let delta: GroupRow["delta"] = null;
      if (period === "month") {
        const card = cards.get(key);
        if (card)
          delta = {
            pct: card.delta_percentage,
            isNew: card.is_new,
            label: "vs 3-mo avg",
          };
      } else if (hasPrior) {
        const prior = sumMonths(
          data.comparison_monthly_group_spending.filter(
            (x) => groupKey(x.group_id) === key,
          ),
          (m) => m <= month,
        );
        delta = {
          pct: prior > 0 ? ((g.amount - prior) / prior) * 100 : 0,
          isNew: prior <= 0,
          label: `vs ${data.year - 1}`,
        };
      }
      const categories = [...g.cats.values()].sort(
        (a, b) => b.amount - a.amount,
      );
      return {
        key,
        name: g.name,
        color: groupColor(ctx, groupId),
        trend: trendFor(data.monthly_group_spending, key),
        priorTrend: hasPrior
          ? trendFor(data.comparison_monthly_group_spending, key)
          : null,
        amount: g.amount,
        share: total > 0 ? g.amount / total : 0,
        delta,
        transactionCount: g.count,
        categories,
        link: {
          range: ctx.range,
          scope: ctx.scope,
          categoryNames: categories.map((c) => c.name),
        },
      };
    });
}

// ─── Notable ───

export type NotableKind = "up" | "down" | "new" | "streak" | "refund";

export interface NotableItem {
  id: string;
  kind: NotableKind;
  /** Sentence without the amount, e.g. "Dining Out up 20% vs its 3-month average". */
  text: string;
  amount: number;
  link: TransactionsLink;
}

/** Three or more consecutive months moving at least 5% the same way. */
export function detectCreep(
  points: TrendPoint[],
  through: number,
): { direction: "up" | "down"; months: number } | null {
  const sorted = points
    .filter((p) => p.month <= through)
    .sort((a, b) => a.month - b.month);
  if (sorted.length < 4) return null;
  for (const direction of ["up", "down"] as const) {
    let streak = 0;
    for (let i = sorted.length - 1; i > 0; i--) {
      const prev = sorted[i - 1]?.amount ?? 0;
      const curr = sorted[i]?.amount ?? 0;
      if (prev <= 0) break;
      const pct = ((curr - prev) / Math.abs(prev)) * 100;
      if (direction === "up" ? pct >= 5 : pct <= -5) streak++;
      else break;
    }
    if (streak >= 3) return { direction, months: streak };
  }
  return null;
}

export const MAX_NOTABLE = 5;

export function buildNotable(
  data: SpendingTrendsResponse,
  ctx: FlowContext,
): NotableItem[] {
  const items: NotableItem[] = [];
  const catLink = (category: string): TransactionsLink => ({
    range: ctx.range,
    scope: ctx.scope,
    categoryNames: [category],
  });
  const settled = data.category_comparisons.filter((c) => !c.is_new);

  const up = settled
    .filter((c) => c.delta_amount > 0)
    .sort((a, b) => b.delta_amount - a.delta_amount)[0];
  if (up)
    items.push({
      id: `up:${up.category}`,
      kind: "up",
      text: `${up.category} up ${Math.round(up.delta_percentage)}% vs its 3-month average`,
      amount: up.current_month_amount,
      link: catLink(up.category),
    });

  const down = settled
    .filter((c) => c.delta_amount < 0 && c.trailing_average > 0)
    .sort((a, b) => a.delta_amount - b.delta_amount)[0];
  if (down)
    items.push({
      id: `down:${down.category}`,
      kind: "down",
      text: `${down.category} down ${Math.abs(Math.round(down.delta_percentage))}% vs its 3-month average`,
      amount: down.current_month_amount,
      link: catLink(down.category),
    });

  for (const fresh of data.category_comparisons
    .filter((c) => c.is_new && c.current_month_amount > 0)
    .sort((a, b) => b.current_month_amount - a.current_month_amount)
    .slice(0, 2))
    items.push({
      id: `new:${fresh.category}`,
      kind: "new",
      text: `${fresh.category} is new this month`,
      amount: fresh.current_month_amount,
      link: catLink(fresh.category),
    });

  for (const row of buildGroupRows(data, "month", ctx)) {
    const creep = detectCreep(row.trend, data.month);
    if (!creep) continue;
    items.push({
      id: `streak:${row.key}`,
      kind: "streak",
      text: `${row.name} ${creep.direction} ${creep.months} months in a row`,
      amount: row.amount,
      link: row.link,
    });
  }

  const refund = data.category_comparisons
    .filter((c) => c.current_month_amount < 0)
    .sort((a, b) => a.current_month_amount - b.current_month_amount)[0];
  if (refund)
    items.push({
      id: `refund:${refund.category}`,
      kind: "refund",
      text: `${refund.category} netted a refund this month`,
      amount: refund.current_month_amount,
      link: catLink(refund.category),
    });

  return items.slice(0, MAX_NOTABLE);
}
