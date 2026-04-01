import { describe, expect, it } from "vitest";
import type { TransactionResponse } from "@/api/generated/model";
import {
  cycleSortState,
  DEFAULT_SORT,
  DISCUSS_TAG,
  hasDiscussTag,
  type SortState,
  sortList,
} from "@/lib/transaction-filters";

// ─── cycleSortState ───

describe("cycleSortState", () => {
  it("clicking a new non-date field sets asc", () => {
    const result = cycleSortState(DEFAULT_SORT, "merchant");
    expect(result).toEqual({ field: "merchant", dir: "asc" });
  });

  it("clicking a new date field sets desc", () => {
    const current: SortState = { field: "merchant", dir: "asc" };
    const result = cycleSortState(current, "date");
    expect(result).toEqual({ field: "date", dir: "desc" });
  });

  it("clicking same field toggles asc → desc", () => {
    const current: SortState = { field: "merchant", dir: "asc" };
    const result = cycleSortState(current, "merchant");
    expect(result).toEqual({ field: "merchant", dir: "desc" });
  });

  it("clicking same field toggles desc → default", () => {
    const current: SortState = { field: "merchant", dir: "desc" };
    const result = cycleSortState(current, "merchant");
    expect(result).toEqual(DEFAULT_SORT);
  });

  it("full cycle: new field → asc → desc → default", () => {
    let state = DEFAULT_SORT;
    state = cycleSortState(state, "amount");
    expect(state).toEqual({ field: "amount", dir: "asc" });

    state = cycleSortState(state, "amount");
    expect(state).toEqual({ field: "amount", dir: "desc" });

    state = cycleSortState(state, "amount");
    expect(state).toEqual(DEFAULT_SORT);
  });
});

// ─── sortList ───

function makeTx(overrides: Partial<TransactionResponse>): TransactionResponse {
  return {
    id: "1",
    date: "2025-01-15",
    merchant: "Grocery Store",
    category: "Groceries",
    account: "Chase",
    amount: -50,
    notes: "",
    tags: [],
    payer_person_id: "p1",
    payer_percentage: 50,
    household: true,
    is_excluded: false,
    original_date: null,
    original_amount: null,
    ...overrides,
  };
}

describe("sortList", () => {
  const groups = new Map([
    ["Groceries", "Food & Dining"],
    ["Gas", "Auto & Transport"],
    ["Rent", "Home Expenses"],
  ]);

  it("sorts by date desc (default) with merchant tiebreaker", () => {
    const txs = [
      makeTx({ id: "1", date: "2025-01-10", merchant: "Beta" }),
      makeTx({ id: "2", date: "2025-01-15", merchant: "Alpha" }),
      makeTx({ id: "3", date: "2025-01-10", merchant: "Alpha" }),
    ];
    const sorted = sortList(txs, { field: "date", dir: "desc" }, groups);
    // desc reverses entire comparison including tiebreaker: Beta before Alpha
    expect(sorted.map((t) => t.id)).toEqual(["2", "1", "3"]);
  });

  it("sorts by date asc with merchant tiebreaker", () => {
    const txs = [
      makeTx({ id: "1", date: "2025-01-15", merchant: "Alpha" }),
      makeTx({ id: "2", date: "2025-01-10", merchant: "Beta" }),
      makeTx({ id: "3", date: "2025-01-10", merchant: "Alpha" }),
    ];
    const sorted = sortList(txs, { field: "date", dir: "asc" }, groups);
    expect(sorted.map((t) => t.id)).toEqual(["3", "2", "1"]);
  });

  it("sorts by merchant alphabetically", () => {
    const txs = [
      makeTx({ id: "1", merchant: "Costco" }),
      makeTx({ id: "2", merchant: "Amazon" }),
      makeTx({ id: "3", merchant: "Whole Foods" }),
    ];
    const sorted = sortList(txs, { field: "merchant", dir: "asc" }, groups);
    expect(sorted.map((t) => t.id)).toEqual(["2", "1", "3"]);
  });

  it("sorts by amount using absolute value", () => {
    const txs = [
      makeTx({ id: "1", amount: -100 }),
      makeTx({ id: "2", amount: 25 }),
      makeTx({ id: "3", amount: -50 }),
    ];
    const sorted = sortList(txs, { field: "amount", dir: "asc" }, groups);
    expect(sorted.map((t) => t.id)).toEqual(["2", "3", "1"]);
  });

  it("sorts by amount desc", () => {
    const txs = [
      makeTx({ id: "1", amount: -100 }),
      makeTx({ id: "2", amount: 25 }),
      makeTx({ id: "3", amount: -50 }),
    ];
    const sorted = sortList(txs, { field: "amount", dir: "desc" }, groups);
    expect(sorted.map((t) => t.id)).toEqual(["1", "3", "2"]);
  });

  it("sorts by category group using the map", () => {
    const txs = [
      makeTx({ id: "1", category: "Rent" }),
      makeTx({ id: "2", category: "Gas" }),
      makeTx({ id: "3", category: "Groceries" }),
    ];
    const sorted = sortList(txs, { field: "group", dir: "asc" }, groups);
    // Auto & Transport < Food & Dining < Home Expenses
    expect(sorted.map((t) => t.id)).toEqual(["2", "3", "1"]);
  });

  it("unmapped categories sort as 'Uncategorized'", () => {
    const txs = [
      makeTx({ id: "1", category: "Gas" }),
      makeTx({ id: "2", category: "Unknown" }),
    ];
    const sorted = sortList(txs, { field: "group", dir: "asc" }, groups);
    // Auto & Transport < Uncategorized
    expect(sorted.map((t) => t.id)).toEqual(["1", "2"]);
  });

  it("does not mutate the input array", () => {
    const txs = [
      makeTx({ id: "1", merchant: "B" }),
      makeTx({ id: "2", merchant: "A" }),
    ];
    const original = [...txs];
    sortList(txs, { field: "merchant", dir: "asc" }, groups);
    expect(txs.map((t) => t.id)).toEqual(original.map((t) => t.id));
  });
});

// ─── Notes & Discuss filter helpers ───

describe("notes and discuss counts", () => {
  const txs = [
    makeTx({ id: "1", notes: "dinner plans", tags: ["shared"] }),
    makeTx({ id: "2", notes: "", tags: [DISCUSS_TAG, "shared"] }),
    makeTx({ id: "3", notes: "ask about this", tags: [DISCUSS_TAG] }),
    makeTx({ id: "4", notes: "", tags: ["shared"] }),
  ];

  it("counts transactions with non-empty notes", () => {
    const count = txs.filter((tx) => tx.notes !== "").length;
    expect(count).toBe(2);
  });

  it("counts transactions with discuss tag", () => {
    const count = txs.filter((tx) => hasDiscussTag(tx)).length;
    expect(count).toBe(2);
  });

  it("hasNotes filter returns only annotated transactions", () => {
    const filtered = txs.filter((tx) => tx.notes !== "");
    expect(filtered.map((t) => t.id)).toEqual(["1", "3"]);
  });

  it("discuss filter returns only flagged transactions", () => {
    const filtered = txs.filter((tx) => hasDiscussTag(tx));
    expect(filtered.map((t) => t.id)).toEqual(["2", "3"]);
  });

  it("discuss tag matching is case-insensitive", () => {
    const mixed = [
      makeTx({ id: "a", tags: ["Discuss"] }),
      makeTx({ id: "b", tags: ["DISCUSS"] }),
      makeTx({ id: "c", tags: ["discuss"] }),
      makeTx({ id: "d", tags: ["shared"] }),
    ];
    const filtered = mixed.filter((tx) => hasDiscussTag(tx));
    expect(filtered.map((t) => t.id)).toEqual(["a", "b", "c"]);
  });

  it("both filters combined returns intersection", () => {
    const filtered = txs.filter((tx) => tx.notes !== "" && hasDiscussTag(tx));
    expect(filtered.map((t) => t.id)).toEqual(["3"]);
  });
});
