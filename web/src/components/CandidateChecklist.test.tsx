import { describe, expect, it } from "vitest";
import {
  computeSettlementAmount,
  type SelectedCandidate,
} from "@/components/CandidateChecklist";

function candidate(overrides: Partial<SelectedCandidate>): SelectedCandidate {
  return {
    id: "1",
    amount: -50,
    merchant: "Venmo",
    payer_person_id: "p1",
    ...overrides,
  };
}

describe("computeSettlementAmount", () => {
  it("returns 0 for no selection", () => {
    expect(computeSettlementAmount([])).toBe(0);
  });

  it("sums two same-sign transfers to exact cents (no float dust)", () => {
    // 10.12 + 10.25 float-sums to 20.369999999999997
    const selected = [
      candidate({ id: "1", amount: -10.12 }),
      candidate({ id: "2", amount: -10.25 }),
    ];
    expect(computeSettlementAmount(selected)).toBe(20.37);
  });

  it("takes the larger side of a debit/credit pair", () => {
    const selected = [
      candidate({ id: "1", amount: -95.5 }),
      candidate({ id: "2", amount: 95.5, payer_person_id: "p2" }),
    ];
    expect(computeSettlementAmount(selected)).toBe(95.5);
  });
});
