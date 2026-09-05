import {
  type TransactionScope,
  TX_FILTER_PARAMS,
} from "@/lib/transaction-filters";

/** A single month, or an explicit inclusive date range (YYYY-MM-DD). */
export type TransactionsRange =
  | { year: number; month: number }
  | { startDate: string; endDate: string };

/** Everything a cross-page link into Transactions can pre-apply. */
export interface TransactionsLink {
  range: TransactionsRange;
  /** Omitted or "all" leaves the scope param off. */
  scope?: TransactionScope;
  payerId?: string;
  /** Category names, not group ids — Transactions filters by `cat=`. */
  categoryNames?: readonly string[];
  /** Free-text search (merchant, category, notes). */
  query?: string;
  settlement?: boolean;
}

/**
 * The one builder for links into the Transactions page. Param order is
 * stable (range, scope, payer, cat…, q, settlement) so hrefs are comparable.
 */
export function buildTransactionsUrl({
  range,
  scope,
  payerId,
  categoryNames,
  query,
  settlement,
}: TransactionsLink): string {
  const params = new URLSearchParams();
  if ("year" in range) {
    params.set("year", String(range.year));
    params.set("month", String(range.month));
  } else {
    params.set("startDate", range.startDate);
    params.set("endDate", range.endDate);
  }
  if (scope && scope !== "all") params.set(TX_FILTER_PARAMS.scope, scope);
  if (payerId) params.append(TX_FILTER_PARAMS.payer, payerId);
  for (const cat of categoryNames ?? [])
    params.append(TX_FILTER_PARAMS.category, cat);
  if (query) params.set(TX_FILTER_PARAMS.query, query);
  if (settlement) params.set(TX_FILTER_PARAMS.settlement, "1");
  return `/transactions?${params.toString()}`;
}
