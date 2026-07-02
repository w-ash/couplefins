import { describe, expect, it } from "vitest";
import type { TransactionResponse } from "@/api/generated/model";
import {
  bucketTransactions,
  computeScopeCounts,
  cycleSortState,
  DEFAULT_SORT,
  DISCUSS_TAG,
  hasDiscussTag,
  isInPersonalScope,
  isInSpottedScope,
  isSettlementLinked,
  type SortState,
  sortList,
  sumNet,
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
    is_settlement: false,
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

// ─── isInPersonalScope ───

describe("isInPersonalScope", () => {
  const me = "p1";
  const partner = "p2";

  it("excludes household transactions regardless of split", () => {
    const tx = makeTx({
      household: true,
      payer_person_id: me,
      payer_percentage: 50,
    });
    expect(isInPersonalScope(tx, me)).toBe(false);
  });

  it("excludes spotted-for-other (I paid, my share is 0)", () => {
    const tx = makeTx({
      household: false,
      payer_person_id: me,
      payer_percentage: 0,
    });
    expect(isInPersonalScope(tx, me)).toBe(false);
  });

  it("includes spotted-for-me (partner paid, partner's share is 0 → mine is 100)", () => {
    const tx = makeTx({
      household: false,
      payer_person_id: partner,
      payer_percentage: 0,
    });
    expect(isInPersonalScope(tx, me)).toBe(true);
  });

  it("includes my pure personal (I paid, my share is 100)", () => {
    const tx = makeTx({
      household: false,
      payer_person_id: me,
      payer_percentage: 100,
    });
    expect(isInPersonalScope(tx, me)).toBe(true);
  });

  it("excludes their pure personal (partner paid, partner's share is 100 → mine is 0)", () => {
    const tx = makeTx({
      household: false,
      payer_person_id: partner,
      payer_percentage: 100,
    });
    expect(isInPersonalScope(tx, me)).toBe(false);
  });

  it("includes a 50/50 non-household split when I am the payer", () => {
    const tx = makeTx({
      household: false,
      payer_person_id: me,
      payer_percentage: 50,
    });
    expect(isInPersonalScope(tx, me)).toBe(true);
  });

  it("includes a 50/50 non-household split when partner is the payer", () => {
    const tx = makeTx({
      household: false,
      payer_person_id: partner,
      payer_percentage: 50,
    });
    expect(isInPersonalScope(tx, me)).toBe(true);
  });

  it("falls back to !household when identity is not yet hydrated", () => {
    const personal = makeTx({ household: false, payer_percentage: 0 });
    const household = makeTx({ household: true });
    expect(isInPersonalScope(personal, null)).toBe(true);
    expect(isInPersonalScope(household, null)).toBe(false);
  });
});

// ─── isInSpottedScope ───

describe("isInSpottedScope", () => {
  const me = "p1";
  const partner = "p2";

  it("includes I-paid-zero-share non-household (I spotted them)", () => {
    const tx = makeTx({
      household: false,
      payer_person_id: me,
      payer_percentage: 0,
    });
    expect(isInSpottedScope(tx, me)).toBe(true);
  });

  it("excludes I-paid-zero-share household (household guard wins)", () => {
    const tx = makeTx({
      household: true,
      payer_person_id: me,
      payer_percentage: 0,
    });
    expect(isInSpottedScope(tx, me)).toBe(false);
  });

  it("excludes partner-paid-zero-share (defensive — partner spotted me)", () => {
    const tx = makeTx({
      household: false,
      payer_person_id: partner,
      payer_percentage: 0,
    });
    expect(isInSpottedScope(tx, me)).toBe(false);
  });

  it("excludes my pure personal (I paid, my share is 100)", () => {
    const tx = makeTx({
      household: false,
      payer_person_id: me,
      payer_percentage: 100,
    });
    expect(isInSpottedScope(tx, me)).toBe(false);
  });

  it("excludes a non-household 50/50 split where I paid", () => {
    const tx = makeTx({
      household: false,
      payer_person_id: me,
      payer_percentage: 50,
    });
    expect(isInSpottedScope(tx, me)).toBe(false);
  });

  it("returns false when identity is not yet hydrated", () => {
    const tx = makeTx({
      household: false,
      payer_person_id: me,
      payer_percentage: 0,
    });
    expect(isInSpottedScope(tx, null)).toBe(false);
  });
});

// ─── bucketTransactions ───

describe("bucketTransactions", () => {
  const me = "p1";
  const partner = "p2";

  it("classifies one tx into each canonical bucket", () => {
    const txs = [
      // household with split (settlement-relevant)
      makeTx({
        id: "h1",
        amount: -100,
        household: true,
        payer_person_id: me,
        payer_percentage: 50,
      }),
      // household paid in full (no split)
      makeTx({
        id: "h2",
        amount: -60,
        household: true,
        payer_person_id: partner,
        payer_percentage: 100,
      }),
      // personal split (rare)
      makeTx({
        id: "ps",
        amount: -40,
        household: false,
        payer_person_id: me,
        payer_percentage: 70,
      }),
      // pure personal
      makeTx({
        id: "pp",
        amount: -25,
        household: false,
        payer_person_id: me,
        payer_percentage: 100,
      }),
      // spotted (I fronted for partner)
      makeTx({
        id: "sp",
        amount: -10,
        household: false,
        payer_person_id: me,
        payer_percentage: 0,
      }),
      // excluded (any shape)
      makeTx({ id: "ex", amount: -5, is_excluded: true }),
    ];
    const b = bucketTransactions(txs, me);

    expect(b.total).toEqual({ count: 6, amount: 240 });
    expect(b.household).toEqual({ count: 2, amount: 160 });
    expect(b.personal).toEqual({ count: 2, amount: 65 });
    expect(b.personalSplit).toEqual({ count: 1, amount: 40 });
    expect(b.spotted).toEqual({ count: 1, amount: 10 });
    expect(b.excluded).toEqual({ count: 1, amount: 5 });
    expect(b.partnerPaid).toEqual({ count: 0, amount: 0 });
  });

  it("counts a positive household amount as a refund sub-bucket", () => {
    const txs = [
      makeTx({
        id: "r",
        amount: 30,
        household: true,
        payer_person_id: me,
        payer_percentage: 50,
      }),
    ];
    const b = bucketTransactions(txs, me);
    expect(b.householdRefunds).toEqual({ count: 1, amount: 30 });
    expect(b.household).toEqual({ count: 1, amount: 30 });
  });

  it("routes non-household partner-paid rows to partnerPaid", () => {
    const tx = makeTx({
      household: false,
      payer_person_id: partner,
      payer_percentage: 50,
    });
    const b = bucketTransactions([tx], me);
    expect(b.partnerPaid.count).toBe(1);
    expect(b.spotted.count).toBe(0);
    expect(b.personal.count).toBe(0);
  });

  it("buckets sum to total for non-overlapping rows", () => {
    const txs = [
      makeTx({
        id: "1",
        amount: -100,
        household: true,
        payer_percentage: 50,
      }),
      makeTx({
        id: "2",
        amount: -25,
        household: false,
        payer_person_id: me,
        payer_percentage: 100,
      }),
      makeTx({
        id: "3",
        amount: -10,
        household: false,
        payer_person_id: me,
        payer_percentage: 0,
      }),
      makeTx({ id: "4", amount: -5, is_excluded: true }),
    ];
    const b = bucketTransactions(txs, me);
    const sum =
      b.household.amount +
      b.personal.amount +
      b.spotted.amount +
      b.partnerPaid.amount +
      b.excluded.amount;
    expect(sum).toBeCloseTo(b.total.amount, 2);
  });
});

// ─── computeScopeCounts ───

describe("computeScopeCounts", () => {
  const me = "p1";
  const partner = "p2";

  it("returns counts for each scope based on the same dataset", () => {
    const txs = [
      makeTx({ id: "h", household: true }),
      makeTx({
        id: "p",
        household: false,
        payer_person_id: me,
        payer_percentage: 100,
      }),
      makeTx({
        id: "s",
        household: false,
        payer_person_id: me,
        payer_percentage: 0,
      }),
      makeTx({
        id: "x",
        household: false,
        payer_person_id: partner,
        payer_percentage: 100,
      }),
    ];
    const counts = computeScopeCounts(txs, me);
    expect(counts).toEqual({ all: 4, household: 1, personal: 1, spotted: 1 });
  });
});

// ─── isSettlementLinked ───

describe("isSettlementLinked", () => {
  it("returns true when tx.is_settlement is true", () => {
    expect(isSettlementLinked(makeTx({ is_settlement: true }))).toBe(true);
  });

  it("returns false for the default fixture (is_settlement=false)", () => {
    expect(isSettlementLinked(makeTx({}))).toBe(false);
  });
});

// ─── sumNet ───

describe("sumNet", () => {
  it("returns positive net spending for a list of expenses", () => {
    const txs = [makeTx({ amount: -100 }), makeTx({ amount: -25 })];
    expect(sumNet(txs)).toBe(125);
  });

  it("subtracts refunds (positive amounts) from spending", () => {
    const txs = [makeTx({ amount: -100 }), makeTx({ amount: 30 })];
    expect(sumNet(txs)).toBe(70);
  });

  it("returns 0 for an empty list", () => {
    expect(sumNet([])).toBe(0);
  });

  it("collapses float dust to exactly 0", () => {
    // -(-0.1 + -0.2 + 0.3) = -5.551115123125783e-17 in JS floats.
    const txs = [
      makeTx({ amount: -0.1 }),
      makeTx({ amount: -0.2 }),
      makeTx({ amount: 0.3 }),
    ];
    expect(sumNet(txs)).toBe(0);
  });
});
