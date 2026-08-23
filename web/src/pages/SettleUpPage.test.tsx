import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { useIdentityStore } from "@/lib/identity";
import { server } from "@/test/server";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "../test/test-utils";
import { SettleUpPage } from "./SettleUpPage";

// Ledger fixtures ride the current year so the year-scoped hero card
// resolves the same way every year the suite runs.
const Y = new Date().getFullYear();

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
  year: Y,
  month: 3,
  owed: { amount: 50.0, from_person_id: "p2", to_person_id: "p1" },
  recorded_settlements: [],
  outstanding: { amount: 50.0, from_person_id: "p2", to_person_id: "p1" },
  outstanding_span: {
    start: { year: Y, month: 3 },
    end: { year: Y, month: 3 },
  },
  ledger_months: [
    {
      year: Y,
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
  latest_transaction_month: { year: Y, month: 3 },
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
  settled_at: `${Y}-04-02T12:00:00Z`,
  created_at: `${Y}-04-02T12:00:00Z`,
  linked_transaction_ids: [],
  linked_transactions: [],
  covered: [
    { year: Y, month: 3, amount: 142.0 },
    { year: Y, month: 4, amount: 58.0 },
  ],
  unapplied: 0.0,
};

const multiMonthResponse = {
  ...settleUpResponse,
  owed: { amount: 142.0, from_person_id: "p2", to_person_id: "p1" },
  outstanding: { amount: 642.0, from_person_id: "p2", to_person_id: "p1" },
  outstanding_span: {
    start: { year: Y, month: 4 },
    end: { year: Y, month: 5 },
  },
  ledger_months: [
    {
      year: Y,
      month: 3,
      gross: { amount: 142.0, from_person_id: "p2", to_person_id: "p1" },
      applied: 142.0,
      remaining: 0.0,
      status: "settled",
      covering_settlement_ids: ["s1"],
      is_offset: false,
    },
    {
      year: Y,
      month: 4,
      gross: { amount: 300.0, from_person_id: "p2", to_person_id: "p1" },
      applied: 58.0,
      remaining: 242.0,
      status: "partially_settled",
      covering_settlement_ids: ["s1"],
      is_offset: false,
    },
    {
      year: Y,
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
      year: Y,
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
      covered: [{ year: Y, month: 3, amount: 50.0 }],
    },
  ],
};

// Last year's December still carries $80 alongside this year's $642 — the
// hero scopes to one year while the all-time balance stays visible.
const crossYearResponse = {
  ...multiMonthResponse,
  outstanding: { amount: 722.0, from_person_id: "p2", to_person_id: "p1" },
  outstanding_span: {
    start: { year: Y - 1, month: 12 },
    end: { year: Y, month: 5 },
  },
  ledger_months: [
    {
      year: Y - 1,
      month: 12,
      gross: { amount: 80.0, from_person_id: "p2", to_person_id: "p1" },
      applied: 0.0,
      remaining: 80.0,
      status: "carried_forward",
      covering_settlement_ids: [],
      is_offset: false,
    },
    ...multiMonthResponse.ledger_months,
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
  latest_transaction_month: { year: Y, month: 2 },
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
    server.use(
      http.get("/api/v1/settlements/candidates", () => HttpResponse.json([])),
    );
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

  it("defaults the hero to the current year and offers each ledger year", async () => {
    serveSettleUp(crossYearResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByRole("radio", { name: String(Y) })).toBeChecked();
    });

    const hero = within(
      screen.getByRole("region", { name: "Settlement summary" }),
    );
    // Only this year's remainders — last year's $80 is excluded.
    expect(hero.getByText("$642.00")).toBeInTheDocument();
    expect(
      hero.getByRole("radio", { name: String(Y - 1) }),
    ).toBeInTheDocument();
    // The all-time balance ($722) is never shown — only the selected year's.
    expect(hero.queryByText(/722/)).not.toBeInTheDocument();
  });

  it("rescopes the hero when another year is selected", async () => {
    const user = userEvent.setup();
    serveSettleUp(crossYearResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByRole("radio", { name: String(Y) })).toBeChecked();
    });

    await user.click(screen.getByRole("radio", { name: String(Y - 1) }));

    const hero = within(
      screen.getByRole("region", { name: "Settlement summary" }),
    );
    expect(hero.getByText("$80.00")).toBeInTheDocument();
    expect(hero.getByText("covers December")).toBeInTheDocument();
    expect(hero.queryByText("$642.00")).not.toBeInTheDocument();
  });

  it("scopes the Months card to the selected year, oldest first", async () => {
    const user = userEvent.setup();
    serveSettleUp(crossYearResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByRole("radio", { name: String(Y) })).toBeChecked();
    });

    // This year's rows only, March through May in calendar order.
    const monthsCard = within(
      screen
        .getByRole("heading", { name: "Months" })
        .closest("div") as HTMLElement,
    );
    expect(
      monthsCard
        .getAllByRole("button")
        .map((el) => el.textContent?.match(/^[A-Z][a-z]+ \d{4}/)?.[0])
        .filter(Boolean),
    ).toEqual([`March ${Y}`, `April ${Y}`, `May ${Y}`]);

    await user.click(screen.getByRole("radio", { name: String(Y - 1) }));

    expect(
      screen.getByRole("button", { name: new RegExp(`December ${Y - 1}`) }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: new RegExp(`May ${Y}`) }),
    ).not.toBeInTheDocument();
  });

  it("waives only the selected year", async () => {
    const user = userEvent.setup();
    let waived: Record<string, unknown> | null = null;
    serveSettleUp(crossYearResponse);
    server.use(
      http.post("/api/v1/settlements/waive", async ({ request }) => {
        waived = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { settlement: {}, warnings: [] },
          { status: 201 },
        );
      }),
    );

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByRole("radio", { name: String(Y) })).toBeChecked();
    });
    // The copy names the year and its amount, never the all-time total.
    expect(screen.getByText(`Waive Bob's ${Y} balance`)).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`\\$642\\.00 from ${Y} will be forgiven`)),
    ).toBeInTheDocument();

    await user.click(screen.getByText("Waive Balance"));

    await waitFor(() => {
      expect(waived).not.toBeNull();
    });
    expect(waived).toMatchObject({ waive_year: Y });
  });

  it("shows only the settlements covering the selected year", async () => {
    const user = userEvent.setup();
    serveSettleUp(crossYearResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText("Settlement History")).toBeInTheDocument();
    });
    // The catch-up payment covered March and April of this year.
    expect(screen.getByText(/Covered Mar \+ Apr/)).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: String(Y - 1) }));

    expect(screen.queryByText("Settlement History")).not.toBeInTheDocument();
  });

  it("renders one row per ledger month with derived status", async () => {
    serveSettleUp(multiMonthResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: new RegExp(`March ${Y}`) }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/settled Apr 2/)).toBeInTheDocument();
    expect(screen.getByText(/partial — \$242\.00 left/)).toBeInTheDocument();
    expect(screen.getByText("carried forward")).toBeInTheDocument();
  });

  it("opens the month from the URL with its drill-down expanded", async () => {
    serveSettleUp(multiMonthResponse);

    renderWithProviders(<SettleUpPage />, {
      routerProps: { initialEntries: [`/settle?year=${Y}&month=4`] },
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: new RegExp(`April ${Y}`) }),
      ).toHaveAttribute("aria-expanded", "true");
    });
    expect(screen.getByText("Lock Month")).toBeInTheDocument();
    expect(screen.getByText("Summary")).toBeInTheDocument();
  });

  it("defaults to the newest month when the current month has no ledger row", async () => {
    serveSettleUp(multiMonthResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: new RegExp(`May ${Y}`) }),
      ).toHaveAttribute("aria-expanded", "true");
    });
    // The drill-down waits for the month-scoped refetch before rendering.
    await waitFor(() => {
      expect(screen.getByText("Lock Month")).toBeInTheDocument();
    });
  });

  it("still offers lock and export for a selected month with no ledger row", async () => {
    // Months 3–5 have settlement activity; deep-link to June (no ledger row).
    serveSettleUp(multiMonthResponse);

    renderWithProviders(<SettleUpPage />, {
      routerProps: { initialEntries: [`/settle?year=${Y}&month=6`] },
    });

    await waitFor(() => {
      expect(
        screen.getByText(new RegExp(`No settlement activity for June ${Y}`)),
      ).toBeInTheDocument();
    });
    // A settlement-free month is still lockable and exportable (US-CLOSE-1/2).
    expect(screen.getByText("Lock Month")).toBeInTheDocument();
    expect(
      screen.getByText("Export adjustments to Monarch"),
    ).toBeInTheDocument();
  });

  it("collapses the expanded month on click", async () => {
    serveSettleUp(multiMonthResponse);
    const user = userEvent.setup();

    renderWithProviders(<SettleUpPage />, {
      routerProps: { initialEntries: [`/settle?year=${Y}&month=4`] },
    });

    await waitFor(() => {
      expect(screen.getByText("Lock Month")).toBeInTheDocument();
    });

    await user.click(
      screen.getByRole("button", { name: new RegExp(`April ${Y}`) }),
    );

    await waitFor(() => {
      expect(screen.queryByText("Lock Month")).not.toBeInTheDocument();
    });
    expect(
      screen.getByRole("button", { name: new RegExp(`April ${Y}`) }),
    ).toHaveAttribute("aria-expanded", "false");
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
            { year: Y, month: 3, amount: 142.0 },
            { year: Y, month: 4, amount: 300.0 },
            { year: Y, month: 5, amount: 400.0 },
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

  it("shows the year as settled and hides ledger actions when nothing is outstanding", async () => {
    serveSettleUp(allSettledResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText(`${Y} is settled`)).toBeInTheDocument();
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
    const user = userEvent.setup();
    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText("Link bank transactions")).toBeInTheDocument();
    });
    expect(screen.getByText("Waive Balance")).toBeInTheDocument();

    // The candidate search starts collapsed — its month stepper appears once
    // the user opens it.
    expect(screen.queryByText("All months")).not.toBeInTheDocument();
    await user.click(await screen.findByText("No matching transfers found"));
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

    expect(screen.queryByText(/is settled$/)).not.toBeInTheDocument();
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
      expect(screen.getByText(`View February ${Y}`)).toBeInTheDocument();
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
