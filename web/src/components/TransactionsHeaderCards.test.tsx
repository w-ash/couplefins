import { describe, expect, it } from "vitest";
import type { OwedAmountResponse } from "@/api/generated/model";
import { settlementDescription } from "./TransactionsHeaderCards";

const ALICE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const BOB_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";

const charged: OwedAmountResponse = {
  amount: 50,
  from_person_id: ALICE_ID,
  to_person_id: BOB_ID,
};

const paid = (amount: number): OwedAmountResponse => ({
  amount,
  from_person_id: ALICE_ID,
  to_person_id: BOB_ID,
});

describe("settlementDescription", () => {
  it("reports what covered a settled month", () => {
    expect(
      settlementDescription({
        status: "settled",
        charged,
        paid: paid(50),
        coveringCount: 1,
      }),
    ).toBe("Covered by 1 settlement · $50.00 paid");
  });

  it("pluralizes multiple covering settlements", () => {
    expect(
      settlementDescription({
        status: "settled",
        charged,
        paid: paid(50),
        coveringCount: 2,
      }),
    ).toBe("Covered by 2 settlements · $50.00 paid");
  });

  it("reports no activity when a settled month has no charges", () => {
    expect(
      settlementDescription({
        status: "settled",
        charged: null,
        paid: null,
        coveringCount: 0,
      }),
    ).toBe("No transactions to settle this period");
  });

  it("shows charged and paid for a partially settled month", () => {
    expect(
      settlementDescription({
        status: "partially_settled",
        charged,
        paid: paid(20),
        coveringCount: 1,
      }),
    ).toBe("$50.00 charged · $20.00 paid (1 settlement)");
  });

  it("marks an untouched month as carried forward", () => {
    expect(
      settlementDescription({
        status: "carried_forward",
        charged,
        paid: null,
        coveringCount: 0,
      }),
    ).toBe("$50.00 charged · no payments recorded");
  });
});
