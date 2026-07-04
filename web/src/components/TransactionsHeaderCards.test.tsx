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
  it("reports a waived balance as waived, not as a linked payment", () => {
    // A waiver forgives the debt — it must not read as "$X linked".
    expect(
      settlementDescription({
        isSettled: true,
        grossDirection: gross,
        linkedCount: 0,
        linkedTotal: 0,
        waivedCount: 1,
      }),
    ).toBe("Balance waived");
  });

  it("pluralizes multiple waivers", () => {
    expect(
      settlementDescription({
        isSettled: true,
        grossDirection: gross,
        linkedCount: 0,
        linkedTotal: 0,
        waivedCount: 2,
      }),
    ).toBe("2 balances waived");
  });

  it("reports linked transfers with their real total", () => {
    expect(
      settlementDescription({
        isSettled: true,
        grossDirection: gross,
        linkedCount: 1,
        linkedTotal: 50,
        waivedCount: 0,
      }),
    ).toBe("1 settlement linked · $50.00");
  });

  it("prefers the linked line when both transfers and waivers exist", () => {
    expect(
      settlementDescription({
        isSettled: true,
        grossDirection: gross,
        linkedCount: 1,
        linkedTotal: 50,
        waivedCount: 1,
      }),
    ).toBe("1 settlement linked · $50.00");
  });
});
