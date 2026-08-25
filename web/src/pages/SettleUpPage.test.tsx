import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type {
  LedgerMonthResponse,
  LedgerSettlementResponse,
} from "@/api/generated/model";
import { useIdentityStore } from "@/lib/identity";
import { makeLedgerMonth, makeLedgerSettlement } from "@/test/ledger-fixtures";
import { server } from "@/test/server";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "../test/test-utils";
import { SettleUpPage } from "./SettleUpPage";

// Fixtures ride the current year so the year-scoped hero resolves the same
// way every year the suite runs. The numbers mirror production 2026: rent
// settled 1:1 each month, so every month swings to Ash's favor.
const Y = new Date().getFullYear();

const ASH = "p1";
const KEW = "p2";

const persons = [
  {
    id: ASH,
    name: "Ash",
    adjustment_account: "",
    theme_preference: "system",
    chat_voice: "fiona",
  },
  {
    id: KEW,
    name: "Kew",
    adjustment_account: "",
    theme_preference: "system",
    chat_voice: "fiona",
  },
];

const uploadedStatuses = [
  { person_id: ASH, person_name: "Ash", has_uploaded: true, upload_count: 1 },
  { person_id: KEW, person_name: "Kew", has_uploaded: true, upload_count: 1 },
];

const ashOwesKew = (amount: number) => ({
  amount,
  from_person_id: ASH,
  to_person_id: KEW,
});
const kewOwesAsh = (amount: number) => ({
  amount,
  from_person_id: KEW,
  to_person_id: ASH,
});

// One $1,981 rent settlement (Ash's half of the rent Check), one portion at
// its rent month.
function rentSettlement(
  id: string,
  month: number,
  overrides: Partial<LedgerSettlementResponse> = {},
): LedgerSettlementResponse {
  return makeLedgerSettlement({
    id,
    amount: 1981.0,
    from_person_id: ASH,
    to_person_id: KEW,
    method: "venmo",
    settled_at: `${Y}-04-26T12:00:00Z`,
    created_at: `${Y}-04-26T12:00:00Z`,
    portions: [{ year: Y, month, amount: 1981.0 }],
    ...overrides,
  });
}

function makeMonth(
  overrides: Partial<LedgerMonthResponse>,
): LedgerMonthResponse {
  return makeLedgerMonth({ year: Y, month: 1, ...overrides });
}

// The production acceptance numbers: Jan 24.11 / Feb 1,758.69 / Mar 175.90,
// year 1,958.70 — every month's direction matches the year's, so no row
// names a person.
const productionResponse = {
  year: Y,
  month: 1,
  years: [
    {
      year: Y,
      charged: ashOwesKew(3984.3),
      paid: ashOwesKew(5943.0),
      balance: kewOwesAsh(1958.7),
      span: { start: { year: Y, month: 1 }, end: { year: Y, month: 3 } },
    },
  ],
  months: [
    makeMonth({
      month: 1,
      charged: ashOwesKew(1956.89),
      paid: ashOwesKew(1981.0),
      balance: kewOwesAsh(24.11),
      status: "partially_settled",
    }),
    makeMonth({
      month: 2,
      charged: ashOwesKew(222.31),
      paid: ashOwesKew(1981.0),
      balance: kewOwesAsh(1758.69),
      status: "partially_settled",
    }),
    makeMonth({
      month: 3,
      charged: ashOwesKew(1805.1),
      paid: ashOwesKew(1981.0),
      balance: kewOwesAsh(175.9),
      status: "partially_settled",
    }),
  ],
  settlements: [
    rentSettlement("r1", 1),
    rentSettlement("r2", 2),
    rentSettlement("r3", 3),
  ],
  upload_statuses: uploadedStatuses,
  persons: [
    { id: ASH, name: "Ash" },
    { id: KEW, name: "Kew" },
  ],
  is_finalized: false,
  finalized_at: null,
  transaction_count: 40,
  latest_transaction_month: { year: Y, month: 3 },
  finalization_warnings: [],
  payer_splits: [
    {
      payer_person_id: KEW,
      fronted: 3962.0,
      their_share: 1981.0,
      partner_share: 1981.0,
      transaction_count: 1,
    },
    {
      payer_person_id: ASH,
      fronted: 48.22,
      their_share: 24.11,
      partner_share: 24.11,
      transaction_count: 2,
    },
  ],
  payer_group_splits: [],
};

// Last year's December still carries $80 — scoped behind its own year tab.
const crossYearResponse = {
  ...productionResponse,
  years: [
    {
      year: Y - 1,
      charged: ashOwesKew(80.0),
      paid: null,
      balance: ashOwesKew(80.0),
      span: {
        start: { year: Y - 1, month: 12 },
        end: { year: Y - 1, month: 12 },
      },
    },
    ...productionResponse.years,
  ],
  months: [
    makeMonth({
      year: Y - 1,
      month: 12,
      charged: ashOwesKew(80.0),
      balance: ashOwesKew(80.0),
      status: "carried_forward",
    }),
    ...productionResponse.months,
  ],
};

// Everything paid off: the year still shows its charges but owes nothing.
const allSettledResponse = {
  ...productionResponse,
  years: [
    {
      year: Y,
      charged: ashOwesKew(3984.3),
      paid: ashOwesKew(3984.3),
      balance: null,
      span: { start: { year: Y, month: 1 }, end: { year: Y, month: 3 } },
    },
  ],
  months: productionResponse.months.map((m) => ({
    ...m,
    balance: null,
    status: "settled",
  })),
};

const emptyResponse = {
  ...productionResponse,
  years: [],
  months: [],
  settlements: [],
  upload_statuses: [
    {
      person_id: ASH,
      person_name: "Ash",
      has_uploaded: false,
      upload_count: 0,
    },
    {
      person_id: KEW,
      person_name: "Kew",
      has_uploaded: false,
      upload_count: 0,
    },
  ],
  transaction_count: 0,
  latest_transaction_month: null,
  payer_splits: [],
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

function monthsCard() {
  return within(
    screen
      .getByRole("heading", { name: "Months" })
      .closest("div") as HTMLElement,
  );
}

describe("SettleUpPage", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: ASH });
    server.use(http.get("/api/v1/persons/", () => HttpResponse.json(persons)));
    server.use(
      http.get("/api/v1/settlements/candidates", () => HttpResponse.json([])),
    );
    serveSettleUp(productionResponse);
  });

  it("shows the year balance with its charged/paid working line", async () => {
    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByRole("radio", { name: String(Y) })).toBeChecked();
    });

    const hero = within(
      screen.getByRole("region", { name: "Settlement summary" }),
    );
    expect(hero.getByText("$1,958.70")).toBeInTheDocument();
    expect(hero.getByText("Kew")).toBeInTheDocument();
    expect(hero.getByText("Ash")).toBeInTheDocument();
    expect(hero.getByText("covers Jan–Mar")).toBeInTheDocument();
    expect(
      hero.getByText(`$3,984.30 charged, $5,943.00 paid in ${Y}`),
    ).toBeInTheDocument();
  });

  it("lists the year's months oldest first as bare amounts", async () => {
    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: new RegExp(`January ${Y}`) }),
      ).toBeInTheDocument();
    });

    const rows = monthsCard()
      .getAllByRole("button")
      .filter((el) => /^[A-Z][a-z]+ \d{4}/.test(el.textContent ?? ""));
    expect(
      rows.map((el) => el.textContent?.match(/^[A-Z][a-z]+ \d{4}/)?.[0]),
    ).toEqual([`January ${Y}`, `February ${Y}`, `March ${Y}`]);

    // Every month runs with the year's direction — bare amounts, no names.
    const january = rows[0];
    expect(january.textContent).toContain("$24.11");
    expect(january.textContent).not.toContain("owes");
    expect(rows[1].textContent).toContain("$1,758.69");
    expect(rows[2].textContent).toContain("$175.90");
  });

  it("names the person only on a month that runs against the year", async () => {
    const withSwungMonth = {
      ...productionResponse,
      months: [
        ...productionResponse.months,
        makeMonth({
          month: 4,
          charged: ashOwesKew(120.0),
          balance: ashOwesKew(120.0),
          status: "carried_forward",
          runs_against_year: true,
        }),
      ],
    };
    serveSettleUp(withSwungMonth);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: new RegExp(`April ${Y}`) }),
      ).toBeInTheDocument();
    });

    const april = screen.getByRole("button", {
      name: new RegExp(`April ${Y}`),
    });
    expect(april.textContent).toContain("Ash");
    expect(april.textContent).toContain("owes");
    expect(april.textContent).toContain("$120.00");
    // The other rows stay bare.
    const january = screen.getByRole("button", {
      name: new RegExp(`January ${Y}`),
    });
    expect(january.textContent).not.toContain("owes");
  });

  it("states the same figure in the month row and its drill-down Summary", async () => {
    renderWithProviders(<SettleUpPage />, {
      routerProps: { initialEntries: [`/settle?year=${Y}&month=1`] },
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: new RegExp(`January ${Y}`) }),
      ).toHaveAttribute("aria-expanded", "true");
    });

    const january = screen.getByRole("button", {
      name: new RegExp(`January ${Y}`),
    });
    expect(january.textContent).toContain("$24.11");

    // The Summary narrative reads the same months[] entry as the row.
    await waitFor(() => {
      expect(screen.getByText("Summary")).toBeInTheDocument();
    });
    expect(screen.getByText(/Kew owes Ash \$24\.11/)).toBeInTheDocument();
  });

  it("shows each settlement with its recorded portions", async () => {
    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText("Settlement History")).toBeInTheDocument();
    });

    expect(screen.getAllByText(/Ash paid Kew/)).toHaveLength(3);
    expect(screen.getByText("$1,981.00 → January")).toBeInTheDocument();
    expect(screen.getByText("$1,981.00 → February")).toBeInTheDocument();
    expect(screen.getByText("$1,981.00 → March")).toBeInTheDocument();
  });

  it("shows a catch-up lump's portions month by month", async () => {
    const withLump = {
      ...productionResponse,
      settlements: [
        ...productionResponse.settlements,
        rentSettlement("lump", 1, {
          amount: 800.0,
          portions: [
            { year: Y, month: 1, amount: 500.0 },
            { year: Y, month: 2, amount: 300.0 },
          ],
        }),
      ],
    };
    serveSettleUp(withLump);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByText("$500.00 → Jan + $300.00 → Feb"),
      ).toBeInTheDocument();
    });
  });

  it("rescopes the hero, months, and history when another year is selected", async () => {
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
    expect(hero.queryByText("$1,958.70")).not.toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: new RegExp(`December ${Y - 1}`) }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: new RegExp(`March ${Y}`) }),
    ).not.toBeInTheDocument();

    // No settlement's portions touch the previous year.
    expect(screen.queryByText("Settlement History")).not.toBeInTheDocument();
  });

  it("waives only after the dialog is confirmed", async () => {
    const user = userEvent.setup();
    let waived: Record<string, unknown> | null = null;
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
      expect(screen.getByText(`Waive Kew's ${Y} balance`)).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        `Clears $1,958.70 from ${Y} only. Undo by deleting the waiver.`,
      ),
    ).toBeInTheDocument();
    // Rejected vocabulary never appears.
    expect(screen.queryByText(/forgiven/i)).not.toBeInTheDocument();

    // Opening the dialog fires nothing.
    await user.click(screen.getByRole("button", { name: "Waive Balance" }));
    const dialog = screen.getByRole("dialog");
    expect(
      within(dialog).getByText(
        `Kew owes Ash $1,958.70 for ${Y}. Waiving clears it; other years stay open.`,
      ),
    ).toBeInTheDocument();
    expect(waived).toBeNull();

    // Cancel fires nothing.
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(waived).toBeNull();

    // Confirming posts the selected year.
    await user.click(screen.getByRole("button", { name: "Waive Balance" }));
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Waive Balance",
      }),
    );

    await waitFor(() => {
      expect(waived).not.toBeNull();
    });
    expect(waived).toMatchObject({
      waive_year: Y,
      from_person_id: KEW,
      to_person_id: ASH,
    });
  });

  it("records the linked settlement's covered months", async () => {
    const user = userEvent.setup();
    let recorded: Record<string, unknown> | null = null;
    server.use(
      http.get("/api/v1/settlements/candidates", () =>
        HttpResponse.json([
          {
            id: "t1",
            date: `${Y}-04-26`,
            merchant: "Venmo",
            amount: -1958.7,
            payer_person_id: KEW,
            category: "Transfers",
            score: 90,
            match_reasons: ["amount match"],
          },
          {
            id: "t2",
            date: `${Y}-04-26`,
            merchant: "Venmo",
            amount: 1958.7,
            payer_person_id: ASH,
            category: "Transfers",
            score: 90,
            match_reasons: ["amount match"],
          },
        ]),
      ),
      http.post("/api/v1/settlements", async ({ request }) => {
        recorded = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { settlement: rentSettlement("new", 1), warnings: [] },
          { status: 201 },
        );
      }),
    );

    renderWithProviders(<SettleUpPage />, {
      routerProps: { initialEntries: [`/settle?year=${Y}&month=1`] },
    });

    await waitFor(() => {
      expect(screen.getByText("2 matching transfers")).toBeInTheDocument();
    });
    await user.click(screen.getByText("2 matching transfers"));
    await user.click(screen.getAllByRole("checkbox")[0]);

    // The viewed month is the default portion; February joins for a lump.
    expect(
      screen.getByRole("button", { name: `Jan ${Y}`, pressed: true }),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: `Feb ${Y}`, pressed: false }),
    );

    await user.click(
      screen.getByRole("button", { name: /Mark as settlement/ }),
    );

    await waitFor(() => {
      expect(recorded).not.toBeNull();
    });
    expect(recorded).toMatchObject({
      from_person_id: KEW,
      to_person_id: ASH,
      covered_months: [
        { year: Y, month: 1 },
        { year: Y, month: 2 },
      ],
    });
  });

  it("sends the legs' sender and recipient, not the outstanding direction", async () => {
    // Regression: the year balance says Kew owes Ash, but the selected
    // Venmo legs show Ash sent the money — the POST and the success copy
    // must follow the legs.
    const user = userEvent.setup();
    let recorded: Record<string, unknown> | null = null;
    server.use(
      http.get("/api/v1/settlements/candidates", () =>
        HttpResponse.json([
          {
            id: "t1",
            date: `${Y}-07-06`,
            merchant: "Venmo",
            amount: -1981.0,
            payer_person_id: ASH,
            category: "Transfers",
            score: 90,
            match_reasons: ["amount match"],
          },
          {
            id: "t2",
            date: `${Y}-07-06`,
            merchant: "Venmo",
            amount: 1981.0,
            payer_person_id: KEW,
            category: "Transfers",
            score: 90,
            match_reasons: ["amount match"],
          },
        ]),
      ),
      http.post("/api/v1/settlements", async ({ request }) => {
        recorded = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { settlement: rentSettlement("new", 1), warnings: [] },
          { status: 201 },
        );
      }),
    );

    renderWithProviders(<SettleUpPage />, {
      routerProps: { initialEntries: [`/settle?year=${Y}&month=1`] },
    });

    await waitFor(() => {
      expect(screen.getByText("2 matching transfers")).toBeInTheDocument();
    });
    await user.click(screen.getByText("2 matching transfers"));
    await user.click(screen.getAllByRole("checkbox")[0]);
    await user.click(screen.getAllByRole("checkbox")[1]);

    await user.click(
      screen.getByRole("button", { name: /Mark as settlement/ }),
    );

    await waitFor(() => {
      expect(recorded).not.toBeNull();
    });
    expect(recorded).toMatchObject({
      from_person_id: ASH,
      to_person_id: KEW,
    });
    expect(
      await screen.findByText(/Settlement linked — Ash paid Kew \$1,981\.00/),
    ).toBeInTheDocument();
  });

  it("shows the year as settled and hides link and waive actions", async () => {
    serveSettleUp(allSettledResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText(`${Y} is settled`)).toBeInTheDocument();
    });

    expect(
      screen.queryByText("Link bank transactions"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Waive Balance")).not.toBeInTheDocument();
  });

  it("renders each month's status chip", async () => {
    const mixed = {
      ...productionResponse,
      months: [
        makeMonth({
          month: 1,
          balance: null,
          status: "settled",
        }),
        productionResponse.months[1],
        makeMonth({
          month: 5,
          charged: ashOwesKew(400.0),
          balance: ashOwesKew(400.0),
          status: "carried_forward",
        }),
      ],
    };
    serveSettleUp(mixed);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText(/settled Apr 26/)).toBeInTheDocument();
    });
    expect(screen.getByText("partially settled")).toBeInTheDocument();
    expect(screen.getByText("carried forward")).toBeInTheDocument();
  });

  it("opens the month from the URL with its drill-down expanded", async () => {
    renderWithProviders(<SettleUpPage />, {
      routerProps: { initialEntries: [`/settle?year=${Y}&month=2`] },
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: new RegExp(`February ${Y}`) }),
      ).toHaveAttribute("aria-expanded", "true");
    });
    expect(screen.getByText("Lock Month")).toBeInTheDocument();
    expect(screen.getByText("Summary")).toBeInTheDocument();
  });

  it("defaults to the newest month when the current month has no activity row", async () => {
    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: new RegExp(`March ${Y}`) }),
      ).toHaveAttribute("aria-expanded", "true");
    });
    await waitFor(() => {
      expect(screen.getByText("Lock Month")).toBeInTheDocument();
    });
  });

  it("still offers lock and export for a selected month with no activity", async () => {
    renderWithProviders(<SettleUpPage />, {
      routerProps: { initialEntries: [`/settle?year=${Y}&month=6`] },
    });

    await waitFor(() => {
      expect(
        screen.getByText(new RegExp(`No settlement activity for June ${Y}`)),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Lock Month")).toBeInTheDocument();
    expect(
      screen.getByText("Export adjustments to Monarch"),
    ).toBeInTheDocument();
  });

  it("collapses the expanded month on click", async () => {
    const user = userEvent.setup();

    renderWithProviders(<SettleUpPage />, {
      routerProps: { initialEntries: [`/settle?year=${Y}&month=2`] },
    });

    await waitFor(() => {
      expect(screen.getByText("Lock Month")).toBeInTheDocument();
    });

    await user.click(
      screen.getByRole("button", { name: new RegExp(`February ${Y}`) }),
    );

    await waitFor(() => {
      expect(screen.queryByText("Lock Month")).not.toBeInTheDocument();
    });
    expect(
      screen.getByRole("button", { name: new RegExp(`February ${Y}`) }),
    ).toHaveAttribute("aria-expanded", "false");
  });

  it("shows empty state when no transactions or settlement activity exist", async () => {
    serveSettleUp(emptyResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/No transactions to settle for/),
      ).toBeInTheDocument();
      expect(screen.getByText("Upload CSV")).toBeInTheDocument();
    });

    expect(screen.queryByText(/is settled$/)).not.toBeInTheDocument();
  });

  it("shows link to latest month when prior data exists", async () => {
    serveSettleUp(emptyWithPriorDataResponse);

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/No transactions to settle for/),
      ).toBeInTheDocument();
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
