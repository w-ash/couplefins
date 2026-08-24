import { describe, expect, it } from "vitest";
import type { LedgerYearResponse } from "@/api/generated/model";
import { defaultLedgerYear, ledgerYears } from "./ledger";

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
