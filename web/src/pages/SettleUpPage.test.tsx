import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { useIdentityStore } from "@/lib/identity";
import { server } from "@/test/server";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "../test/test-utils";
import { SettleUpPage } from "./SettleUpPage";

const persons = [
  {
    id: "p1",
    name: "Alice",
    adjustment_account: "",
    theme_preference: "system",
    chat_voice: "fiona",
  },
  {
    id: "p2",
    name: "Bob",
    adjustment_account: "",
    theme_preference: "system",
    chat_voice: "fiona",
  },
];

const uploadedStatuses = [
  {
    person_id: "p1",
    person_name: "Alice",
    has_uploaded: true,
    upload_count: 1,
  },
  {
    person_id: "p2",
    person_name: "Bob",
    has_uploaded: true,
    upload_count: 1,
  },
];

// One carried-forward month, no payments: outstanding equals the month's
// gross and the span is that single month.
const settleUpResponse = {
  year: 2026,
  month: 3,
  owed: { amount: 50.0, from_person_id: "p2", to_person_id: "p1" },
  recorded_settlements: [],
  outstanding: { amount: 50.0, from_person_id: "p2", to_person_id: "p1" },
  outstanding_span: {
    start: { year: 2026, month: 3 },
    end: { year: 2026, month: 3 },
  },
  ledger_months: [
    {
      year: 2026,
      month: 3,
      gross: { amount: 50.0, from_person_id: "p2", to_person_id: "p1" },
      applied: 0.0,
      remaining: 50.0,
      status: "carried_forward",
      covering_settlement_ids: [],
      is_offset: false,
    },
  ],
  all_settlements: [],
  upload_statuses: uploadedStatuses,
  persons: [
    { id: "p1", name: "Alice" },
    { id: "p2", name: "Bob" },
  ],
  is_finalized: false,
  finalized_at: null,
  transaction_count: 5,
  latest_transaction_month: { year: 2026, month: 3 },
  finalization_warnings: [],
  payer_splits: [],
  payer_group_splits: [],
};

// Three months + one catch-up payment: Mar fully covered (settled), Apr
// partially covered, May untouched. Sum of remainders = outstanding (642),
// payment coverage slices (142 + 58) = payment amount (200), no unapplied.
const catchUpPayment = {
  id: "s1",
  year: null,
  month: null,
  amount: 200.0,
  from_person_id: "p2",
  to_person_id: "p1",
  method: "venmo",
  is_waived: false,
  notes: "",
  settled_at: "2026-04-02T12:00:00Z",
  created_at: "2026-04-02T12:00:00Z",
  linked_transaction_ids: [],
  linked_transactions: [],
  covered: [
    { year: 2026, month: 3, amount: 142.0 },
    { year: 2026, month: 4, amount: 58.0 },
  ],
  unapplied: 0.0,
};

const multiMonthResponse = {
  ...settleUpResponse,
  owed: { amount: 142.0, from_person_id: "p2", to_person_id: "p1" },
  outstanding: { amount: 642.0, from_person_id: "p2", to_person_id: "p1" },
  outstanding_span: {
    start: { year: 2026, month: 4 },
    end: { year: 2026, month: 5 },
  },
  ledger_months: [
    {
      year: 2026,
      month: 3,
      gross: { amount: 142.0, from_person_id: "p2", to_person_id: "p1" },
      applied: 142.0,
      remaining: 0.0,
      status: "settled",
      covering_settlement_ids: ["s1"],
      is_offset: false,
    },
    {
      year: 2026,
      month: 4,
      gross: { amount: 300.0, from_person_id: "p2", to_person_id: "p1" },
      applied: 58.0,
      remaining: 242.0,
      status: "partially_settled",
      covering_settlement_ids: ["s1"],
      is_offset: false,
    },
    {
      year: 2026,
      month: 5,
      gross: { amount: 400.0, from_person_id: "p2", to_person_id: "p1" },
      applied: 0.0,
      remaining: 400.0,
      status: "carried_forward",
      covering_settlement_ids: [],
      is_offset: false,
    },
  ],
  all_settlements: [catchUpPayment],
  recorded_settlements: [],
  payer_splits: [
    {
      payer_person_id: "p1",
      fronted: 100,
      their_share: 50,
      partner_share: 50,
      transaction_count: 1,
    },
    {
      payer_person_id: "p2",
      fronted: 0,
      their_share: 0,
      partner_share: 0,
      transaction_count: 0,
    },
  ],
};

// Everything paid off: the single month's gross is fully covered by one
// payment, so nothing is outstanding and the span is null.
const allSettledResponse = {
  ...settleUpResponse,
  outstanding: null,
  outstanding_span: null,
  ledger_months: [
    {
      year: 2026,
      month: 3,
      gross: { amount: 50.0, from_person_id: "p2", to_person_id: "p1" },
      applied: 50.0,
      remaining: 0.0,
      status: "settled",
      covering_settlement_ids: ["s2"],
      is_offset: false,
    },
  ],
  all_settlements: [
    {
      ...catchUpPayment,
      id: "s2",
      amount: 50.0,
      covered: [{ year: 2026, month: 3, amount: 50.0 }],
    },
  ],
};

const emptyResponse = {
  ...settleUpResponse,
  owed: null,
  recorded_settlements: [],
  outstanding: null,
  outstanding_span: null,
  ledger_months: [],
  all_settlements: [],
  upload_statuses: [
    {
      person_id: "p1",
      person_name: "Alice",
      has_uploaded: false,
      upload_count: 0,
    },
    {
      person_id: "p2",
      person_name: "Bob",
      has_uploaded: false,
      upload_count: 0,
    },
  ],
  transaction_count: 0,
  latest_transaction_month: null,
};

const emptyWithPriorDataResponse = {
  ...emptyResponse,
  latest_transaction_month: { year: 2026, month: 2 },
};

// Echo the requested year/month back so any drill-down month resolves as
// "ready" — mirrors the real API, whose month-scoped fields follow params.
function serveSettleUp(fixture: Record<string, unknown>) {
  server.use(
    http.get("/api/v1/settle-up", ({ request }) => {
      const url = new URL(request.url);
      return HttpResponse.json({
        ...fixture,
        year: Number(url.searchParams.get("year")),
        month: Number(url.searchParams.get("month")),
      });
    }),
  );
}

describe("SettleUpPage", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: "p1" });
    server.use(http.get("/api/v1/persons/", () => HttpResponse.json(persons)));
    serveSettleUp(settleUpResponse);
  });

  it("shows the total outstanding balance with its covered span", async () => {
    serveSettleUp(multiMonthResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getAllByText(/owes/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("$642.00")).toBeInTheDocument();
      expect(screen.getByText("covers Apr–May")).toBeInTheDocument();
    });
  });

  it("renders one row per ledger month with derived status", async () => {
    serveSettleUp(multiMonthResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /March 2026/ }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/settled Apr 2/)).toBeInTheDocument();
    expect(screen.getByText(/partial — \$242\.00 left/)).toBeInTheDocument();
    expect(screen.getByText("carried forward")).toBeInTheDocument();
  });

  it("opens the month from the URL with its drill-down expanded", async () => {
    serveSettleUp(multiMonthResponse);

    renderWithProviders(<SettleUpPage />, {
      routerProps: { initialEntries: ["/settle?year=2026&month=4"] },
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /April 2026/ }),
      ).toHaveAttribute("aria-expanded", "true");
    });
    expect(screen.getByText("Lock Month")).toBeInTheDocument();
    expect(screen.getByText("Showing the work")).toBeInTheDocument();
  });

  it("defaults to the newest month when the current month has no ledger row", async () => {
    serveSettleUp(multiMonthResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /May 2026/ })).toHaveAttribute(
        "aria-expanded",
        "true",
      );
    });
    // The drill-down waits for the month-scoped refetch before rendering.
    await waitFor(() => {
      expect(screen.getByText("Lock Month")).toBeInTheDocument();
    });
  });

  it("collapses the expanded month on click", async () => {
    serveSettleUp(multiMonthResponse);
    const user = userEvent.setup();

    renderWithProviders(<SettleUpPage />, {
      routerProps: { initialEntries: ["/settle?year=2026&month=4"] },
    });

    await waitFor(() => {
      expect(screen.getByText("Lock Month")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /April 2026/ }));

    await waitFor(() => {
      expect(screen.queryByText("Lock Month")).not.toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /April 2026/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("shows payment history with FIFO coverage", async () => {
    serveSettleUp(multiMonthResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText(/Bob paid Alice/)).toBeInTheDocument();
    });
    expect(screen.getByText("Covered Mar + Apr")).toBeInTheDocument();
  });

  it("notes the unapplied part of an overpayment", async () => {
    const overpaid = {
      ...multiMonthResponse,
      outstanding: null,
      outstanding_span: null,
      ledger_months: multiMonthResponse.ledger_months.map((m) => ({
        ...m,
        applied: m.gross.amount,
        remaining: 0.0,
        status: "settled",
        covering_settlement_ids: ["s1"],
      })),
      all_settlements: [
        {
          ...catchUpPayment,
          amount: 892.0,
          covered: [
            { year: 2026, month: 3, amount: 142.0 },
            { year: 2026, month: 4, amount: 300.0 },
            { year: 2026, month: 5, amount: 400.0 },
          ],
          unapplied: 50.0,
        },
      ],
    };
    serveSettleUp(overpaid);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/\$50\.00 not applied — increases the balance/),
      ).toBeInTheDocument();
    });
  });

  it("shows 'All settled!' and hides ledger actions when nothing is outstanding", async () => {
    serveSettleUp(allSettledResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText("All settled!")).toBeInTheDocument();
    });

    // Payments apply to the running ledger — with nothing outstanding there
    // is nothing to link or waive.
    expect(
      screen.queryByText("Link bank transactions"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Waive Balance")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/No transactions to settle for/),
    ).not.toBeInTheDocument();
  });

  it("offers link and waive actions while a balance is outstanding", async () => {
    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText("Link bank transactions")).toBeInTheDocument();
    });
    expect(screen.getByText("Waive Balance")).toBeInTheDocument();
    expect(screen.getByText("All months")).toBeInTheDocument();
  });

  it("shows empty state when no transactions or ledger activity exist", async () => {
    serveSettleUp(emptyResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/No transactions to settle for/),
      ).toBeInTheDocument();
      expect(screen.getByText("Upload CSV")).toBeInTheDocument();
    });

    expect(screen.queryByText("All settled!")).not.toBeInTheDocument();
    expect(screen.queryByText(/View /)).not.toBeInTheDocument();
  });

  it("shows link to latest month when prior data exists", async () => {
    serveSettleUp(emptyWithPriorDataResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/No transactions to settle for/),
      ).toBeInTheDocument();
      expect(screen.getByText("Upload CSV")).toBeInTheDocument();
      expect(screen.getByText("View February 2026")).toBeInTheDocument();
    });
  });

  it("shows upload statuses in empty state", async () => {
    serveSettleUp(emptyResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getAllByText("not yet")).toHaveLength(2);
    });
  });
});
