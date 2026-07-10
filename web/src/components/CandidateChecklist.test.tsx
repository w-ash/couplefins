import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import {
  CandidateChecklist,
  computeSettlementAmount,
  type SelectedCandidate,
} from "@/components/CandidateChecklist";
import { server } from "@/test/server";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "../test/test-utils";

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

describe("month stepper", () => {
  it("steps forward without bound when the ceiling is unknown", async () => {
    // latest_transaction_month only covers household rows, so it can be
    // null while later-dated settlement candidates still exist — forward
    // navigation must stay available.
    server.use(
      http.get("/api/v1/settlements/candidates", () => HttpResponse.json([])),
    );

    renderWithProviders(
      <CandidateChecklist
        amount="50"
        initialSearchMonth={{ year: 2026, month: 3 }}
        searchFloor={null}
        persons={[{ id: "p1", name: "Alice" }]}
        selectedIds={[]}
        onSelectionChange={() => {}}
        latestTransactionMonth={null}
      />,
    );

    const nextButton = await screen.findByRole("button", {
      name: "Next month",
    });
    expect(nextButton).toBeEnabled();

    await userEvent.click(nextButton);
    await waitFor(() => {
      expect(screen.getByText("April 2026")).toBeInTheDocument();
    });
  });
});
