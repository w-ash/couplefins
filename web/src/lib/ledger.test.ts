import { describe, expect, it } from "vitest";
import type { LedgerYearResponse } from "@/api/generated/model";
import { defaultLedgerYear, formatPortionPeriod, ledgerYears } from "./ledger";

const Y = new Date().getFullYear();

const ASH = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const KEW = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";

function makeYear(overrides: Partial<LedgerYearResponse>): LedgerYearResponse {
  return {
    year: Y,
    charged: null,
    paid: null,
    balance: null,
    span: null,
    ...overrides,
  };
}

const owed = (amount: number) => ({
  amount,
  from_person_id: KEW,
  to_person_id: ASH,
});

describe("ledgerYears", () => {
  it("lists the served years oldest first", () => {
    // The API pads the list with the current year itself.
    expect(
      ledgerYears([
        makeYear({ year: Y }),
        makeYear({ year: Y - 1, charged: owed(100) }),
        makeYear({ year: Y - 2, charged: owed(50) }),
      ]),
    ).toEqual([Y - 2, Y - 1, Y]);
  });

  it("offers the current year even with no data at all", () => {
    expect(ledgerYears([])).toEqual([Y]);
  });
});

describe("defaultLedgerYear", () => {
  it("opens on the current year when it has activity", () => {
    expect(
      defaultLedgerYear([
        makeYear({ year: Y - 1, balance: owed(80) }),
        makeYear({ year: Y, charged: owed(100), balance: owed(100) }),
      ]),
    ).toBe(Y);
  });

  it("falls back to the oldest year still carrying a balance when the current year is empty", () => {
    // The January case: no rows for this year yet, last year still owes.
    expect(
      defaultLedgerYear([
        makeYear({ year: Y - 2, charged: owed(50), balance: owed(50) }),
        makeYear({ year: Y - 1, charged: owed(80), balance: owed(80) }),
        makeYear({ year: Y }),
      ]),
    ).toBe(Y - 2);
  });

  it("falls back to the newest year with activity when everything is settled", () => {
    expect(
      defaultLedgerYear([
        makeYear({ year: Y - 2, charged: owed(50) }),
        makeYear({ year: Y - 1, charged: owed(80), paid: owed(80) }),
        makeYear({ year: Y }),
      ]),
    ).toBe(Y - 1);
  });

  it("defaults to the current year when there is no data", () => {
    expect(defaultLedgerYear([])).toBe(Y);
  });
});

describe("formatPortionPeriod", () => {
  const p = (month: number, year = Y, amount = 100) => ({
    year,
    month,
    amount,
  });

  it("names a single covered month in full", () => {
    expect(formatPortionPeriod([p(1)], Y)).toBe("January");
  });

  it("collapses three or more consecutive months to a span", () => {
    expect(formatPortionPeriod([p(1), p(2), p(3)], Y)).toBe("Jan – Mar");
  });

  it("collapses a whole waived year to one span", () => {
    const all = Array.from({ length: 12 }, (_, i) => p(i + 1));
    expect(formatPortionPeriod(all, Y)).toBe("Jan – Dec");
  });

  it("lists two consecutive months rather than spanning them", () => {
    expect(formatPortionPeriod([p(1), p(2)], Y)).toBe("Jan, Feb");
  });

  it("caps a scattered set at three months and counts the rest", () => {
    expect(formatPortionPeriod([p(1), p(3), p(5), p(7), p(9)], Y)).toBe(
      "Jan, Mar, May +2",
    );
  });

  it("carries the year for a month outside the year being viewed", () => {
    expect(formatPortionPeriod([p(12, Y - 1)], Y)).toBe(`Dec ${Y - 1}`);
  });

  it("spans a year boundary", () => {
    expect(formatPortionPeriod([p(11, Y - 1), p(12, Y - 1), p(1)], Y)).toBe(
      `Nov ${Y - 1} – Jan`,
    );
  });

  it("orders portions the API sent out of sequence", () => {
    expect(formatPortionPeriod([p(3), p(1), p(2)], Y)).toBe("Jan – Mar");
  });

  it("ignores the sign — a negative portion still covers its month", () => {
    expect(formatPortionPeriod([p(1, Y, 900), p(2, Y, -100)], Y)).toBe(
      "Jan, Feb",
    );
  });

  it("falls back to a dash when nothing was recorded", () => {
    expect(formatPortionPeriod([], Y)).toBe("—");
  });
});
