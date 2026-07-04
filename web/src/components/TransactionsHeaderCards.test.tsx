import { describe, expect, it } from "vitest";
import type { OwedAmountResponse } from "@/api/generated/model";
import { settlementDescription } from "./TransactionsHeaderCards";

const ALICE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const BOB_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";

const gross: OwedAmountResponse = {
  amount: 50,
  from_person_id: ALICE_ID,
  to_person_id: BOB_ID,
};

describe("settlementDescription", () => {
  it("reports what covered a settled month", () => {
    expect(
      settlementDescription({
        status: "settled",
        gross,
        applied: 50,
        coveringCount: 1,
        isOffset: false,
      }),
    ).toBe("Covered by 1 settlement · $50.00 applied");
  });

  it("pluralizes multiple covering settlements", () => {
    expect(
      settlementDescription({
        status: "settled",
        gross,
        applied: 50,
        coveringCount: 2,
        isOffset: false,
      }),
    ).toBe("Covered by 2 settlements · $50.00 applied");
  });

  it("labels a month offset by opposing balances", () => {
    expect(
      settlementDescription({
        status: "settled",
        gross,
        applied: 50,
        coveringCount: 0,
        isOffset: true,
      }),
    ).toBe("Offset against other months' balances");
  });

  it("reports no activity when a settled month has no gross", () => {
    expect(
      settlementDescription({
        status: "settled",
        gross: null,
        applied: 0,
        coveringCount: 0,
        isOffset: false,
      }),
    ).toBe("No transactions to settle this period");
  });

  it("shows gross and applied for a partially settled month", () => {
    expect(
      settlementDescription({
        status: "partially_settled",
        gross,
        applied: 20,
        coveringCount: 1,
        isOffset: false,
      }),
    ).toBe("Gross $50.00 · $20.00 applied (1 settlement)");
  });

  it("marks an untouched month as carried forward", () => {
    expect(
      settlementDescription({
        status: "carried_forward",
        gross,
        applied: 0,
        coveringCount: 0,
        isOffset: false,
      }),
    ).toBe("Gross $50.00 · carried forward on the ledger");
  });
});
