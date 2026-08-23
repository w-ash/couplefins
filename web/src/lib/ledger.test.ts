import { describe, expect, it } from "vitest";
import type { LedgerMonthResponse } from "@/api/generated/model";
import {
  combineOwed,
  defaultLedgerYear,
  ledgerYears,
  settlementsForYear,
  summarizeLedgerYear,
} from "@/lib/ledger";

function month(
  year: number,
  monthNumber: number,
  grossAmount: number,
  remaining: number,
  from = "p2",
): LedgerMonthResponse {
  return {
    year,
    month: monthNumber,
    gross: {
      amount: grossAmount,
      from_person_id: from,
      to_person_id: from === "p2" ? "p1" : "p2",
    },
    applied: grossAmount - remaining,
    remaining,
    status: remaining === 0 ? "settled" : "carried_forward",
    covering_settlement_ids: [],
    is_offset: false,
  };
}

describe("combineOwed", () => {
  it("nets opposing directions", () => {
    expect(
      combineOwed([
        { amount: 100, from_person_id: "p2", to_person_id: "p1" },
        { amount: 30, from_person_id: "p1", to_person_id: "p2" },
      ]),
    ).toEqual({ amount: 70, from_person_id: "p2", to_person_id: "p1" });
  });

  it("flips direction when the opposing side wins", () => {
    expect(
      combineOwed([
        { amount: 30, from_person_id: "p2", to_person_id: "p1" },
        { amount: 100, from_person_id: "p1", to_person_id: "p2" },
      ]),
    ).toEqual({ amount: 70, from_person_id: "p1", to_person_id: "p2" });
  });

  it("returns null for an empty or net-zero set", () => {
    expect(combineOwed([])).toBeNull();
    expect(
      combineOwed([
        { amount: 50, from_person_id: "p2", to_person_id: "p1" },
        { amount: 50, from_person_id: "p1", to_person_id: "p2" },
      ]),
    ).toBeNull();
  });
});

describe("summarizeLedgerYear", () => {
  const months = [
    month(2025, 11, 100, 0),
    month(2025, 12, 200, 50),
    month(2026, 1, 300, 300),
    month(2026, 3, 400, 100),
  ];

  it("sums gross and remaining for the selected year only", () => {
    const summary = summarizeLedgerYear(months, 2026);
    expect(summary.gross).toEqual({
      amount: 700,
      from_person_id: "p2",
      to_person_id: "p1",
    });
    expect(summary.outstanding).toEqual({
      amount: 400,
      from_person_id: "p2",
      to_person_id: "p1",
    });
  });

  it("spans only the months that still carry a balance", () => {
    expect(summarizeLedgerYear(months, 2026).span).toEqual({
      start: { year: 2026, month: 1 },
      end: { year: 2026, month: 3 },
    });
    expect(summarizeLedgerYear(months, 2025).span).toEqual({
      start: { year: 2025, month: 12 },
      end: { year: 2025, month: 12 },
    });
  });

  it("reports a fully covered year as settled with its gross intact", () => {
    const summary = summarizeLedgerYear([month(2024, 5, 100, 0)], 2024);
    expect(summary.outstanding).toBeNull();
    expect(summary.span).toBeNull();
    expect(summary.gross?.amount).toBe(100);
  });

  it("is empty for a year with no ledger rows", () => {
    const summary = summarizeLedgerYear(months, 2023);
    expect(summary.gross).toBeNull();
    expect(summary.outstanding).toBeNull();
  });

  it("year outstanding sums back to the all-time balance", () => {
    const total = [2025, 2026]
      .map((y) => summarizeLedgerYear(months, y).outstanding?.amount ?? 0)
      .reduce((a, b) => a + b, 0);
    expect(total).toBe(450);
  });
});

describe("ledgerYears", () => {
  it("offers every ledger year plus the current one, oldest first", () => {
    const thisYear = new Date().getFullYear();
    expect(
      ledgerYears([month(2024, 1, 10, 10), month(2025, 1, 10, 10)]),
    ).toEqual([...new Set([2024, 2025, thisYear])].sort((a, b) => a - b));
  });

  it("offers the current year for an empty ledger", () => {
    expect(ledgerYears([])).toEqual([new Date().getFullYear()]);
  });
});

describe("defaultLedgerYear", () => {
  const thisYear = new Date().getFullYear();

  it("opens on the current year once it has ledger rows", () => {
    expect(
      defaultLedgerYear([
        month(thisYear - 1, 12, 200, 50),
        month(thisYear, 1, 300, 300),
      ]),
    ).toBe(thisYear);
  });

  it("opens on the oldest year that still owes when this year is empty", () => {
    expect(
      defaultLedgerYear([
        month(thisYear - 2, 5, 100, 0),
        month(thisYear - 1, 12, 200, 50),
      ]),
    ).toBe(thisYear - 1);
  });

  it("opens on the newest year when everything is settled", () => {
    expect(
      defaultLedgerYear([
        month(thisYear - 2, 5, 100, 0),
        month(thisYear - 1, 5, 100, 0),
      ]),
    ).toBe(thisYear - 1);
  });

  it("falls back to the current year for an empty ledger", () => {
    expect(defaultLedgerYear([])).toBe(thisYear);
  });
});

describe("settlementsForYear", () => {
  function settlement(
    id: string,
    settledAt: string,
    covered: Array<{ year: number; month: number }>,
  ) {
    return {
      id,
      year: null,
      month: null,
      amount: 100,
      from_person_id: "p2",
      to_person_id: "p1",
      method: "venmo",
      is_waived: false,
      notes: "",
      settled_at: settledAt,
      created_at: settledAt,
      linked_transaction_ids: [],
      covered: covered.map((c) => ({ ...c, amount: 50 })),
      unapplied: 0,
    };
  }

  const catchUp = settlement("s1", "2026-01-10T00:00:00Z", [
    { year: 2025, month: 12 },
    { year: 2026, month: 1 },
  ]);
  const inYear = settlement("s2", "2026-04-02T00:00:00Z", [
    { year: 2026, month: 3 },
  ]);
  const uncovered = settlement("s3", "2025-06-01T00:00:00Z", []);

  it("keeps a payment in every year its coverage touched", () => {
    const all = [catchUp, inYear, uncovered];
    expect(settlementsForYear(all, 2026).map((s) => s.id)).toEqual([
      "s1",
      "s2",
    ]);
    expect(settlementsForYear(all, 2025).map((s) => s.id)).toEqual([
      "s1",
      "s3",
    ]);
  });

  it("falls back to the recorded year when nothing was covered", () => {
    // A payment that matched no month must still be reachable somewhere.
    expect(settlementsForYear([uncovered], 2026)).toEqual([]);
    expect(settlementsForYear([uncovered], 2025)).toEqual([uncovered]);
  });
});
