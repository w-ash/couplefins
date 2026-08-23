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

describe("disclosure", () => {
  const matches = [
    {
      id: "c1",
      date: "2026-03-04",
      merchant: "Venmo",
      amount: -50,
      payer_person_id: "p1",
      match_reasons: ["exact amount"],
    },
    {
      id: "c2",
      date: "2026-03-04",
      merchant: "Venmo",
      amount: 50,
      payer_person_id: "p2",
      match_reasons: ["exact amount"],
    },
  ];

  function renderChecklist(defaultExpanded: boolean) {
    server.use(
      http.get("/api/v1/settlements/candidates", () =>
        HttpResponse.json(matches),
      ),
    );
    renderWithProviders(
      <CandidateChecklist
        amount="50"
        initialSearchMonth={{ year: 2026, month: 3 }}
        searchFloor={null}
        persons={[
          { id: "p1", name: "Alice" },
          { id: "p2", name: "Bob" },
        ]}
        selectedIds={[]}
        onSelectionChange={() => {}}
        latestTransactionMonth={null}
        defaultExpanded={defaultExpanded}
      />,
    );
  }

  it("hides the candidates behind a summary when collapsed", async () => {
    renderChecklist(false);

    const toggle = await screen.findByRole("button", {
      name: "2 matching transfers",
    });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByText("March 2026")).not.toBeInTheDocument();
  });

  it("opens and closes on the summary", async () => {
    const user = userEvent.setup();
    renderChecklist(false);

    await user.click(
      await screen.findByRole("button", { name: "2 matching transfers" }),
    );
    expect(screen.getAllByRole("checkbox")).toHaveLength(2);
    expect(screen.getByText("March 2026")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "2 matching transfers" }),
    );
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("starts open when the caller asks for it", async () => {
    renderChecklist(true);

    await waitFor(() => {
      expect(screen.getAllByRole("checkbox")).toHaveLength(2);
    });
    expect(
      screen.getByRole("button", { name: "2 matching transfers" }),
    ).toHaveAttribute("aria-expanded", "true");
  });
});
