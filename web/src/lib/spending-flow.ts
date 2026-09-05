import type {
  FlowSourceKind,
  SpendingFlowCellItem,
  TopMerchantItem,
} from "@/api/generated/model";
import { getChartColor } from "@/lib/chart-colors";
import type { PersonScope } from "@/lib/person-scope";
import type {
  TransactionsLink,
  TransactionsRange,
} from "@/lib/transaction-links";

export const UNCATEGORIZED_KEY = "uncategorized";
export const UNCATEGORIZED_COLOR = "var(--color-muted-foreground)";

/** What the flow chart and the legend need to know about the viewer. */
export interface FlowContext {
  range: TransactionsRange;
  scope: PersonScope;
  currentPersonId: string | null;
  personNames: Map<string, string>;
  personIndex: Map<string, number>;
  /** Stable color per group id, see `assignGroupColors`. */
  groupColors: Map<string, string>;
}

export type FlowNodeKind = "source" | "group" | "category" | "other";

export interface FlowNodeDatum {
  /** Stable identity: `source:<kind>:<person>`, `group:<id>`, `category:<name>`, `other:<group id>`. */
  id: string;
  name: string;
  kind: FlowNodeKind;
  color: string;
  amount: number;
  transactionCount: number;
  link: TransactionsLink;
  /** For "Everything else" nodes: the folded category names. */
  members?: string[];
}

export interface FlowLinkDatum {
  source: number;
  target: number;
  value: number;
}

export interface SankeyDataset {
  nodes: FlowNodeDatum[];
  links: FlowLinkDatum[];
  /** Cells whose net was a refund, left out because a flow cannot go backwards. */
  droppedRefundOnly: number;
}

export interface FoldOptions {
  /** Categories with at least this share of the period total always stay. */
  minShare: number;
  /** Per group, keep at most this many categories before folding the rest. */
  maxPerGroup: number;
  /** Across all groups, draw at most this many category nodes; the smallest
   * beyond it fold into their group's "Everything else". */
  maxCategories: number;
}

export const DEFAULT_FOLD: FoldOptions = {
  minShare: 0.03,
  maxPerGroup: 3,
  maxCategories: 14,
};

export function groupKey(groupId: string | null): string {
  return groupId ?? UNCATEGORIZED_KEY;
}

/**
 * One color per group, keyed by group id, assigned in the given order (the
 * year-to-date ranking) so the month and YTD views and every chart agree.
 */
export function assignGroupColors(
  groupIds: ReadonlyArray<string | null>,
): Map<string, string> {
  const colors = new Map<string, string>();
  for (const id of groupIds) {
    const key = groupKey(id);
    if (colors.has(key)) continue;
    colors.set(
      key,
      id === null ? UNCATEGORIZED_COLOR : getChartColor(colors.size),
    );
  }
  return colors;
}

export function groupColor(ctx: FlowContext, groupId: string | null): string {
  return ctx.groupColors.get(groupKey(groupId)) ?? UNCATEGORIZED_COLOR;
}

function personColor(ctx: FlowContext, personId: string): string {
  return `var(--person-${ctx.personIndex.get(personId) ?? 0})`;
}

/** One node per source. The household share is one claim no matter which
 * partner paid the row, so it ignores the payer. */
function sourceId(cell: SpendingFlowCellItem): string {
  if (cell.source_kind === "household_share") return "source:household_share";
  return `source:${cell.source_kind}:${cell.source_person_id}`;
}

/** How a source reads on the page, in the viewer's words. */
export function sourceLabel(
  kind: FlowSourceKind,
  personId: string,
  ctx: FlowContext,
): string {
  const name = ctx.personNames.get(personId) ?? "Unknown";
  switch (kind) {
    case "payer":
      return `${name} paid`;
    case "household_share":
      return "My share of household";
    case "personal":
      return "My personal";
    case "spotted_for_me":
      return `${name} paid for me`;
  }
}

export function sourceColor(
  kind: FlowSourceKind,
  personId: string,
  ctx: FlowContext,
): string {
  if (kind === "household_share") return "var(--household)";
  return personColor(ctx, personId);
}

/** The Transactions list a source node stands for. A person's own sources
 * carry the personal scope; the household share reads best as the household
 * list (its share column shows what counted). */
function sourceLink(
  kind: FlowSourceKind,
  personId: string,
  ctx: FlowContext,
): TransactionsLink {
  if (kind === "household_share")
    return { range: ctx.range, scope: "household" };
  return { range: ctx.range, scope: ctx.scope, payerId: personId };
}

function categoryLink(
  names: readonly string[],
  ctx: FlowContext,
): TransactionsLink {
  return { range: ctx.range, scope: ctx.scope, categoryNames: names };
}

interface CategoryTotal {
  category: string;
  groupId: string | null;
  groupName: string;
  amount: number;
  transactionCount: number;
}

/** Positive per-category totals across sources, largest first. */
function categoryTotals(cells: SpendingFlowCellItem[]): CategoryTotal[] {
  const byCategory = new Map<string, CategoryTotal>();
  for (const cell of cells) {
    const existing = byCategory.get(cell.category);
    if (existing) {
      existing.amount += cell.amount;
      existing.transactionCount += cell.transaction_count;
    } else {
      byCategory.set(cell.category, {
        category: cell.category,
        groupId: cell.group_id,
        groupName: cell.group_name,
        amount: cell.amount,
        transactionCount: cell.transaction_count,
      });
    }
  }
  return [...byCategory.values()]
    .filter((c) => c.amount > 0)
    .sort((a, b) => b.amount - a.amount);
}

export interface FoldedCategories {
  kept: CategoryTotal[];
  folded: CategoryTotal[];
}

/**
 * Per group: keep the biggest categories, fold the long tail into one
 * "Everything else" entry. A single leftover is never folded — the fold
 * would not save anything.
 */
export function foldCategories(
  totals: CategoryTotal[],
  periodTotal: number,
  options: FoldOptions = DEFAULT_FOLD,
): FoldedCategories {
  const kept: CategoryTotal[] = [];
  const folded: CategoryTotal[] = [];
  for (const [i, total] of totals.entries()) {
    const bigEnough =
      periodTotal > 0 && total.amount / periodTotal >= options.minShare;
    if (i < options.maxPerGroup || bigEnough) kept.push(total);
    else folded.push(total);
  }
  if (folded.length === 1) {
    const [only] = folded;
    if (only) kept.push(only);
    return { kept, folded: [] };
  }
  return { kept, folded };
}

/**
 * Sankey nodes and links: sources → groups → categories. Refund-heavy cells
 * are left out (a flow cannot carry a negative), and small categories fold
 * into an "Everything else" node per group.
 */
export function buildSankeyData(
  cells: SpendingFlowCellItem[],
  ctx: FlowContext,
  options: FoldOptions = DEFAULT_FOLD,
): SankeyDataset {
  const positive = cells.filter((c) => c.amount > 0);
  const droppedRefundOnly = cells.length - positive.length;
  const periodTotal = positive.reduce((s, c) => s + c.amount, 0);

  const nodes: FlowNodeDatum[] = [];
  const index = new Map<string, number>();
  const addNode = (node: FlowNodeDatum): number => {
    const existing = index.get(node.id);
    if (existing !== undefined) return existing;
    index.set(node.id, nodes.length);
    nodes.push(node);
    return nodes.length - 1;
  };
  const linkValue = new Map<string, FlowLinkDatum>();
  const addLink = (source: number, target: number, value: number) => {
    const key = `${source}>${target}`;
    const existing = linkValue.get(key);
    if (existing) existing.value += value;
    else linkValue.set(key, { source, target, value });
  };

  // Sources first (left column), largest first.
  const sourceTotals = new Map<string, number>();
  for (const cell of positive)
    sourceTotals.set(
      sourceId(cell),
      (sourceTotals.get(sourceId(cell)) ?? 0) + cell.amount,
    );
  const sourceCells = new Map(positive.map((c) => [sourceId(c), c]));
  for (const [id] of [...sourceTotals.entries()].sort((a, b) => b[1] - a[1])) {
    const cell = sourceCells.get(id);
    if (!cell) continue;
    const kind = cell.source_kind;
    const pid = cell.source_person_id;
    addNode({
      id,
      name: sourceLabel(kind, pid, ctx),
      kind: "source",
      color: sourceColor(kind, pid, ctx),
      amount: sourceTotals.get(id) ?? 0,
      transactionCount: positive
        .filter((c) => sourceId(c) === id)
        .reduce((s, c) => s + c.transaction_count, 0),
      link: sourceLink(kind, pid, ctx),
    });
  }

  // Groups in cell order (already sorted by group total on the server).
  const groups = new Map<string, CategoryTotal[]>();
  for (const total of categoryTotals(positive)) {
    const key = groupKey(total.groupId);
    const list = groups.get(key);
    if (list) list.push(total);
    else groups.set(key, [total]);
  }
  const groupOrder = [...groups.entries()].sort(
    (a, b) =>
      b[1].reduce((s, c) => s + c.amount, 0) -
      a[1].reduce((s, c) => s + c.amount, 0),
  );

  // Fold per group first, then trim the smallest survivors so the right
  // column never exceeds `maxCategories` nodes and labels keep their room.
  const folds = new Map<string, FoldedCategories>();
  for (const [key, totals] of groupOrder)
    folds.set(key, foldCategories(totals, periodTotal, options));
  const survivors = [...folds.entries()]
    .flatMap(([key, f]) => f.kept.map((c) => ({ key, c })))
    .sort((a, b) => a.c.amount - b.c.amount);
  let excess = survivors.length - options.maxCategories;
  for (const { key, c } of survivors) {
    if (excess <= 0) break;
    const fold = folds.get(key);
    if (!fold) continue;
    fold.kept = fold.kept.filter((x) => x !== c);
    fold.folded = [...fold.folded, c].sort((a, b) => b.amount - a.amount);
    excess--;
  }

  for (const [key, totals] of groupOrder) {
    const first = totals[0];
    if (!first) continue;
    const color = groupColor(ctx, first.groupId);
    const groupNode = addNode({
      id: `group:${key}`,
      name: first.groupName,
      kind: "group",
      color,
      amount: totals.reduce((s, c) => s + c.amount, 0),
      transactionCount: totals.reduce((s, c) => s + c.transactionCount, 0),
      link: categoryLink(
        totals.map((c) => c.category),
        ctx,
      ),
    });

    for (const cell of positive) {
      if (groupKey(cell.group_id) !== key) continue;
      const sourceIndex = index.get(sourceId(cell));
      if (sourceIndex !== undefined)
        addLink(sourceIndex, groupNode, cell.amount);
    }

    const { kept, folded } = folds.get(key) ?? { kept: totals, folded: [] };
    for (const total of kept) {
      const categoryNode = addNode({
        id: `category:${total.category}`,
        name: total.category,
        kind: "category",
        color,
        amount: total.amount,
        transactionCount: total.transactionCount,
        link: categoryLink([total.category], ctx),
      });
      addLink(groupNode, categoryNode, total.amount);
    }
    if (folded.length > 0) {
      const members = folded.map((c) => c.category);
      const otherNode = addNode({
        id: `other:${key}`,
        name: `Everything else (${folded.length})`,
        kind: "other",
        color,
        amount: folded.reduce((s, c) => s + c.amount, 0),
        transactionCount: folded.reduce((s, c) => s + c.transactionCount, 0),
        link: categoryLink(members, ctx),
        members,
      });
      addLink(
        groupNode,
        otherNode,
        folded.reduce((s, c) => s + c.amount, 0),
      );
    }
  }

  return { nodes, links: [...linkValue.values()], droppedRefundOnly };
}

// ─── Donut / bars slices ───

export type SliceBy = "group" | "category" | "merchant";

export interface SliceDatum {
  id: string;
  name: string;
  /** Group id (or uncategorized key) for icons and drill-down. */
  groupKey: string | null;
  color: string;
  amount: number;
  share: number;
  transactionCount: number;
  link: TransactionsLink;
  /** Set on an "Everything else" slice: the names it folds. */
  members?: string[];
}

export const DEFAULT_MAX_SLICES = 8;

function withShares(slices: SliceDatum[]): SliceDatum[] {
  const total = slices.reduce((s, x) => s + x.amount, 0);
  return slices.map((s) => ({ ...s, share: total > 0 ? s.amount / total : 0 }));
}

/** Largest first; beyond `maxSlices` everything folds into one entry so
 * the chart stays readable and the long tail stays visible as a number. */
export function foldSlices(
  slices: SliceDatum[],
  ctx: FlowContext,
  maxSlices = DEFAULT_MAX_SLICES,
): SliceDatum[] {
  const sorted = [...slices]
    .filter((s) => s.amount > 0)
    .sort((a, b) => b.amount - a.amount);
  if (sorted.length <= maxSlices + 1) return withShares(sorted);
  const kept = sorted.slice(0, maxSlices);
  const rest = sorted.slice(maxSlices);
  const members = rest.flatMap((s) => s.members ?? [s.name]);
  const categoryNames = rest.flatMap((s) => s.link.categoryNames ?? []);
  kept.push({
    id: "other",
    name: `Everything else (${rest.length})`,
    groupKey: null,
    color: UNCATEGORIZED_COLOR,
    amount: rest.reduce((s, x) => s + x.amount, 0),
    share: 0,
    transactionCount: rest.reduce((s, x) => s + x.transactionCount, 0),
    link:
      categoryNames.length > 0
        ? categoryLink(categoryNames, ctx)
        : { range: ctx.range, scope: ctx.scope },
    members,
  });
  return withShares(kept);
}

export function buildGroupSlices(
  cells: SpendingFlowCellItem[],
  ctx: FlowContext,
): SliceDatum[] {
  const byGroup = new Map<string, SliceDatum>();
  for (const total of categoryTotals(cells)) {
    const key = groupKey(total.groupId);
    const existing = byGroup.get(key);
    if (existing) {
      existing.amount += total.amount;
      existing.transactionCount += total.transactionCount;
      existing.link.categoryNames = [
        ...(existing.link.categoryNames ?? []),
        total.category,
      ];
    } else {
      byGroup.set(key, {
        id: `group:${key}`,
        name: total.groupName,
        groupKey: key,
        color: groupColor(ctx, total.groupId),
        amount: total.amount,
        share: 0,
        transactionCount: total.transactionCount,
        link: categoryLink([total.category], ctx),
      });
    }
  }
  return withShares([...byGroup.values()].sort((a, b) => b.amount - a.amount));
}

export function buildCategorySlices(
  cells: SpendingFlowCellItem[],
  ctx: FlowContext,
  onlyGroupKey?: string,
): SliceDatum[] {
  return withShares(
    categoryTotals(cells)
      .filter(
        (t) =>
          onlyGroupKey === undefined || groupKey(t.groupId) === onlyGroupKey,
      )
      .map((t) => ({
        id: `category:${t.category}`,
        name: t.category,
        groupKey: groupKey(t.groupId),
        color: groupColor(ctx, t.groupId),
        amount: t.amount,
        share: 0,
        transactionCount: t.transactionCount,
        link: categoryLink([t.category], ctx),
      })),
  );
}

export function buildMerchantSlices(
  merchants: TopMerchantItem[],
  ctx: FlowContext,
): SliceDatum[] {
  return withShares(
    merchants
      .filter((m) => m.amount > 0)
      .map((m) => ({
        id: `merchant:${m.merchant}`,
        name: m.merchant,
        groupKey: groupKey(m.group_id),
        color: groupColor(ctx, m.group_id),
        amount: m.amount,
        share: 0,
        transactionCount: m.transaction_count,
        link: { range: ctx.range, scope: ctx.scope, query: m.merchant },
      })),
  );
}
