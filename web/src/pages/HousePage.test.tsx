import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { HouseResponse } from "@/api/generated/model";
import { useIdentityStore } from "@/lib/identity";
import { ALICE_ID, BOB_ID, makeHouseResponse } from "@/test/house-fixtures";
import { server } from "@/test/server";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/test/test-utils";
import { HousePage } from "./HousePage";

function serveHouse(response: HouseResponse) {
  server.use(http.get("/api/v1/house", () => HttpResponse.json(response)));
}

function withExamples(sections: string[]): HouseResponse {
  return {
    ...makeHouseResponse(),
    example_sections: sections,
  } as HouseResponse;
}

const loanRecord = {
  id: "loan-1",
  name: "Family loan",
  slug: "family-loan",
  tag: "loan:family-loan",
  lender: "Example Bank",
  kind: "interest_only",
  principal: 250000,
  annual_rate: 4.5,
  payment: 937.5,
  term_months: 360,
  first_due_on: "2026-01-01",
  statement_balance: 250000,
  statement_balance_as_of: "2026-10-01",
  replaced_by_loan_id: null,
  closed_on: null,
  notes: "",
  created_at: "2026-01-01T00:00:00Z",
};

function loansSection(): HTMLElement {
  return document.querySelector(
    'section[aria-labelledby="house-loans"]',
  ) as HTMLElement;
}

function upcomingSection(): HTMLElement {
  return document.querySelector(
    'section[aria-labelledby="house-upcoming"]',
  ) as HTMLElement;
}

describe("HousePage", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: ALICE_ID });
    server.use(
      http.get("/api/v1/house/manual-entries", () => HttpResponse.json([])),
      http.get("/api/v1/house/loans", () =>
        HttpResponse.json([{ ...loanRecord }]),
      ),
      http.get("/api/v1/house/obligations", () => HttpResponse.json([])),
    );
  });

  it("shows the example notice only for example data", async () => {
    serveHouse(makeHouseResponse());
    const { unmount } = renderWithProviders(<HousePage />);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Example figures",
    );
    unmount();

    serveHouse(makeHouseResponse({ example_sections: [] }));
    renderWithProviders(<HousePage />);
    await screen.findByRole("heading", { name: "Put in" });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("marks only the sections named in example_sections", async () => {
    serveHouse(withExamples(["put_in", "loans"]));
    renderWithProviders(<HousePage />);
    await screen.findByRole("heading", { name: "Put in" });

    expect(screen.getByRole("status")).toHaveTextContent("Example figures");
    const pills = screen.getAllByText("Example");
    expect(pills).toHaveLength(2);
    const sectionOf = (pill: HTMLElement) =>
      pill.closest("section")?.getAttribute("aria-labelledby");
    expect(pills.map(sectionOf)).toEqual(["house-put-in", "house-loans"]);
  });

  it("shows no notice or pills once every section is real", async () => {
    serveHouse(withExamples([]));
    renderWithProviders(<HousePage />);
    await screen.findByRole("heading", { name: "Put in" });

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.queryByText("Example")).not.toBeInTheDocument();
  });

  it("renders the six sections", async () => {
    serveHouse(makeHouseResponse());
    renderWithProviders(<HousePage />);
    for (const name of [
      "Put in",
      "Shares",
      "Loans",
      "Upcoming",
      "Set aside",
      "Recent activity",
    ]) {
      expect(await screen.findByRole("heading", { name })).toBeInTheDocument();
    }
  });

  it("renders served figures", async () => {
    serveHouse(makeHouseResponse());
    renderWithProviders(<HousePage />);
    await screen.findByRole("heading", { name: "Put in" });

    expect(screen.getAllByText("$102,000.00").length).toBeGreaterThan(0);
    expect(screen.getByText("Closing")).toBeInTheDocument();
    expect(screen.getByText("Repairs")).toBeInTheDocument();
    expect(screen.getByText("Deposits not yet spent")).toBeInTheDocument();
    expect(screen.getByText("Short by $450.00")).toBeInTheDocument();
    expect(screen.getAllByText("Tax reserve").length).toBeGreaterThan(0);
    expect(screen.getByText("estimate")).toBeInTheDocument();
    expect(screen.getByText("Deposit")).toBeInTheDocument();
    expect(screen.getByText("Alice $300.00 · Bob $0.00")).toBeInTheDocument();
    expect(screen.getByText("60.0%")).toBeInTheDocument();
    expect(screen.getByText("4.50%")).toBeInTheDocument();
    expect(screen.getAllByText("Joint checking")).toHaveLength(2);
  });

  it("renders real set-aside buckets, the unassigned one last and muted", async () => {
    serveHouse(
      withExamples(["put_in", "loans", "upcoming", "recent_activity"]),
    );
    renderWithProviders(<HousePage />);

    const heading = await screen.findByRole("heading", { name: "Set aside" });
    const section = heading.closest("section") as HTMLElement;
    expect(within(section).queryByText("Example")).not.toBeInTheDocument();
    const [buckets] = within(section).getAllByRole("table");
    const [, body] = within(buckets).getAllByRole("rowgroup");
    const rows = within(body).getAllByRole("row");
    const unassigned = rows[rows.length - 1];
    expect(unassigned).toHaveTextContent("Unassigned");
    expect(within(section).getAllByText("no pot tag")).toEqual([
      within(unassigned).getByText("no pot tag"),
    ]);
    expect(unassigned.firstElementChild).toHaveClass("text-muted-foreground");
    expect(rows[0].firstElementChild).not.toHaveClass("text-muted-foreground");
  });

  it("totals the buckets beside the bank balance and its difference", async () => {
    serveHouse(makeHouseResponse());
    renderWithProviders(<HousePage />);

    const heading = await screen.findByRole("heading", { name: "Set aside" });
    const section = heading.closest("section") as HTMLElement;
    expect(
      within(section).getByText("Total set aside").nextSibling,
    ).toHaveTextContent("$3,590.00");
    expect(
      within(section).getByText("Bank balance").nextSibling,
    ).toHaveTextContent("$3,640.00");
    expect(within(section).getByText(/as of/)).toBeInTheDocument();
    expect(
      within(section).getByText("Difference").nextSibling,
    ).toHaveTextContent("+$50.00");
  });

  it("shows a placeholder when no bank balance is entered", async () => {
    const base = makeHouseResponse();
    serveHouse({
      ...base,
      set_aside: {
        ...base.set_aside,
        bank_balance: null,
        bank_balance_as_of: null,
        difference: null,
      },
    });
    renderWithProviders(<HousePage />);

    const heading = await screen.findByRole("heading", { name: "Set aside" });
    const section = heading.closest("section") as HTMLElement;
    expect(
      within(section).getAllByTitle("Enter the bank balance in House settings"),
    ).toHaveLength(2);
  });

  it("lists each owner's deposits under the buckets", async () => {
    serveHouse(makeHouseResponse());
    renderWithProviders(<HousePage />);

    const table = await screen.findByRole("table", { name: "Deposits" });
    const [, alice, bob] = within(table).getAllByRole("row");
    expect(alice).toHaveTextContent("Alice$4,000.00$0.00$1,825.00$2,175.00");
    expect(bob).toHaveTextContent("Bob$2,200.00$1,000.00$1,785.00$1,415.00");
  });

  it("says so when a list is empty", async () => {
    serveHouse(
      makeHouseResponse({
        loans: [],
        upcoming: [],
        set_aside: {
          buckets: [],
          total: 0,
          bank_balance: null,
          bank_balance_as_of: null,
          difference: null,
          owners: [],
        },
        recent_activity: [],
      }),
    );
    renderWithProviders(<HousePage />);

    expect(
      await screen.findByText("No loans recorded yet."),
    ).toBeInTheDocument();
    expect(screen.getByText("Nothing coming due.")).toBeInTheDocument();
    expect(screen.getByText("No money set aside yet.")).toBeInTheDocument();
    expect(screen.getByText("No activity yet.")).toBeInTheDocument();
  });

  it("points to Settings when no house is set up", async () => {
    serveHouse(makeHouseResponse({ asset: null }));
    renderWithProviders(<HousePage />);

    const banner = (await screen.findByText("No house set up yet")).closest(
      "[role=status]",
    ) as HTMLElement;
    expect(
      within(banner).getByRole("link", { name: "Set up the home in Settings" }),
    ).toHaveAttribute("href", "/settings#settings-house");
  });

  it("shows the asset name and no Example pills on real Put in and Shares", async () => {
    serveHouse(withExamples(["loans", "upcoming"]));
    renderWithProviders(<HousePage />);

    expect(await screen.findByText("Maple Street")).toBeInTheDocument();
    expect(screen.queryByText("No house set up yet")).not.toBeInTheDocument();
    const pills = screen.getAllByText("Example");
    expect(pills).toHaveLength(2);
    for (const id of ["house-put-in", "house-shares"]) {
      const section = document.querySelector(
        `section[aria-labelledby="${id}"]`,
      ) as HTMLElement;
      expect(within(section).queryByText("Example")).not.toBeInTheDocument();
    }
  });

  it("records a credit with the entered split", async () => {
    serveHouse(withExamples([]));
    let body: unknown;
    server.use(
      http.post("/api/v1/house/manual-entries", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<HousePage />);

    await user.click(
      await screen.findByRole("button", { name: "Record a credit" }),
    );
    const dialog = await screen.findByRole("dialog");
    const date = within(dialog).getByLabelText("Date");
    await user.clear(date);
    await user.type(date, "2026-10-01");
    await user.type(within(dialog).getByLabelText("Amount"), "1200");
    await user.selectOptions(
      within(dialog).getByLabelText("Kind"),
      "insurance",
    );
    await user.type(
      within(dialog).getByLabelText("Description"),
      "First premium",
    );
    await user.type(
      within(dialog).getByLabelText("Document reference"),
      "PL-7",
    );
    const alice = within(dialog).getByLabelText(/Alice/);
    await user.clear(alice);
    await user.type(alice, "70");
    await user.click(
      within(dialog).getByRole("button", { name: "Record a credit" }),
    );

    await waitFor(() =>
      expect(body).toEqual({
        account_name: "Escrow",
        date: "2026-10-01",
        amount: 1200,
        description: "First premium",
        document_ref: "PL-7",
        share_kind: "insurance",
        owner_shares: { [ALICE_ID]: 70, [BOB_ID]: 30 },
      }),
    );
  });

  it("sends nothing when the credit dialog is cancelled", async () => {
    serveHouse(withExamples([]));
    let posted = false;
    server.use(
      http.post("/api/v1/house/manual-entries", () => {
        posted = true;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<HousePage />);
    await user.click(
      await screen.findByRole("button", { name: "Record a credit" }),
    );
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(posted).toBe(false);
  });

  it("shows the server message when a credit is refused", async () => {
    serveHouse(withExamples([]));
    server.use(
      http.post("/api/v1/house/manual-entries", () =>
        HttpResponse.json(
          { error: { code: "FINALIZED", message: "Month is finalized" } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<HousePage />);
    await user.click(
      await screen.findByRole("button", { name: "Record a credit" }),
    );
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Amount"), "5");
    await user.type(within(dialog).getByLabelText("Description"), "x");
    await user.click(
      within(dialog).getByRole("button", { name: "Record a credit" }),
    );
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Month is finalized",
    );
  });

  it("lists recorded credits and deletes one after confirming", async () => {
    serveHouse(withExamples([]));
    let deleted: string | undefined;
    server.use(
      http.get("/api/v1/house/manual-entries", () =>
        HttpResponse.json([
          {
            id: "m1",
            account_name: "Escrow",
            date: "2026-09-30",
            amount: 8000,
            description: "Closing costs",
            document_ref: "CD-1",
            share_kind: "closing",
            owner_shares: { [ALICE_ID]: 100, [BOB_ID]: 0 },
          },
        ]),
      ),
      http.delete("/api/v1/house/manual-entries/:id", ({ params }) => {
        deleted = params.id as string;
        return HttpResponse.json({ deleted: true });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<HousePage />);

    expect(await screen.findByText("Closing costs")).toBeInTheDocument();
    expect(screen.getByText(/Alice 100%, Bob 0%/)).toHaveTextContent("CD-1");
    expect(screen.getByText("$8,000.00")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Delete Closing costs" }),
    );
    const dialog = await screen.findByRole("dialog");
    await user.click(
      within(dialog).getByRole("button", { name: "Delete credit" }),
    );
    await waitFor(() => expect(deleted).toBe("m1"));
  });

  it("says so when no credits are recorded", async () => {
    serveHouse(withExamples([]));
    renderWithProviders(<HousePage />);
    expect(
      await screen.findByText("No credits recorded by hand yet."),
    ).toBeInTheDocument();
  });

  describe("loans", () => {
    it("hides loan actions on example data", async () => {
      serveHouse(withExamples(["loans"]));
      renderWithProviders(<HousePage />);
      await screen.findByRole("heading", { name: "Loans" });
      const section = loansSection();

      expect(
        within(section).getByRole("button", { name: "Record a loan" }),
      ).toBeInTheDocument();
      expect(
        within(section).queryByRole("button", { name: /Update statement/ }),
      ).toBeNull();
      expect(
        within(section).queryByRole("button", { name: /^Replace / }),
      ).toBeNull();
      expect(
        within(section).queryByRole("button", { name: /^Close / }),
      ).toBeNull();
      expect(
        within(section).queryByRole("button", { name: /^Delete / }),
      ).toBeNull();
      expect(
        within(section).queryByRole("button", { name: /^Add next / }),
      ).toBeNull();
    });

    it("renders each open loan's figures, statement and tag", async () => {
      serveHouse(withExamples([]));
      renderWithProviders(<HousePage />);
      await screen.findByRole("heading", { name: "Loans" });
      const section = loansSection();

      expect(within(section).getByText("Family loan")).toBeInTheDocument();
      expect(
        within(section).getAllByText("Example Bank").length,
      ).toBeGreaterThan(0);
      expect(within(section).getByText("Interest only")).toBeInTheDocument();
      expect(
        within(section).getByText("Balance").parentElement?.nextSibling,
      ).toHaveTextContent("$250,000.00");
      expect(within(section).getByText("4.50%")).toBeInTheDocument();
      expect(
        within(section).getByText("Payment").parentElement?.nextSibling,
      ).toHaveTextContent("$937.50");
      expect(
        within(section).getByText(/Statement \$250,000.00 as of/),
      ).toBeInTheDocument();
      expect(
        await within(section).findByText("loan:family-loan"),
      ).toBeVisible();
    });

    it("lists past loans under a disclosure with their replacement", async () => {
      serveHouse(withExamples([]));
      renderWithProviders(<HousePage />);
      await screen.findByRole("heading", { name: "Loans" });

      const summary = within(loansSection()).getByText("Past loans (1)");
      expect(summary.tagName).toBe("SUMMARY");
      const details = summary.closest("details") as HTMLElement;
      expect(details).not.toHaveAttribute("open");
      expect(within(details).getByText("Starter loan")).toBeInTheDocument();
      expect(
        within(details).getByText(/replaced by Family loan/),
      ).toBeInTheDocument();
    });

    it("records a loan with the entered terms", async () => {
      serveHouse(withExamples([]));
      let body: unknown;
      server.use(
        http.post("/api/v1/house/loans", async ({ request }) => {
          body = await request.json();
          return HttpResponse.json({}, { status: 201 });
        }),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", { name: "Record a loan" }),
      );
      const dialog = await screen.findByRole("dialog");
      await user.type(within(dialog).getByLabelText("Name"), "Bridge loan");
      await user.type(within(dialog).getByLabelText("Lender"), "Example Bank");
      await user.selectOptions(
        within(dialog).getByLabelText("Kind"),
        "interest_only",
      );
      await user.type(within(dialog).getByLabelText("Principal"), "100000");
      await user.type(within(dialog).getByLabelText("Annual rate (%)"), "5.25");
      await user.type(within(dialog).getByLabelText("Payment"), "437.5");
      await user.type(within(dialog).getByLabelText(/Term/), "120");
      await user.type(
        within(dialog).getByLabelText("First due date"),
        "2026-11-01",
      );
      await user.type(
        within(dialog).getByLabelText("Statement balance"),
        "100000",
      );
      await user.type(
        within(dialog).getByLabelText("Statement date"),
        "2026-10-01",
      );
      await user.click(
        within(dialog).getByRole("button", { name: "Record a loan" }),
      );

      await waitFor(() =>
        expect(body).toEqual({
          name: "Bridge loan",
          lender: "Example Bank",
          kind: "interest_only",
          principal: 100000,
          annual_rate: 5.25,
          payment: 437.5,
          term_months: 120,
          first_due_on: "2026-11-01",
          statement_balance: 100000,
          statement_balance_as_of: "2026-10-01",
          notes: "",
        }),
      );
    });

    it("replaces a loan at refinance, pre-filled from the old one", async () => {
      serveHouse(withExamples([]));
      let posted: { url: string; body: unknown } | undefined;
      server.use(
        http.post("/api/v1/house/loans/:id/replace", async ({ request }) => {
          posted = { url: request.url, body: await request.json() };
          return HttpResponse.json({}, { status: 201 });
        }),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", {
          name: "Replace Family loan at refinance",
        }),
      );
      const dialog = await screen.findByRole("dialog");
      const name = within(dialog).getByLabelText("Name");
      expect(name).toHaveValue("");
      expect(name).toHaveAttribute("placeholder", "New loan name");
      await user.type(name, "Refinanced loan");
      const rate = within(dialog).getByLabelText("Annual rate (%)");
      await user.clear(rate);
      await user.type(rate, "3.75");
      const closed = within(dialog).getByLabelText("Old loan closes on");
      await user.clear(closed);
      await user.type(closed, "2026-10-15");
      await user.click(
        within(dialog).getByRole("button", { name: "Replace at refinance" }),
      );

      await waitFor(() => expect(posted).toBeDefined());
      expect(posted?.url).toContain("/loans/loan-1/replace");
      expect(posted?.body).toMatchObject({
        name: "Refinanced loan",
        annual_rate: 3.75,
        closed_on: "2026-10-15",
      });
    });

    it("posts a new statement balance", async () => {
      serveHouse(withExamples([]));
      let body: unknown;
      server.use(
        http.put("/api/v1/house/loans/:id/statement", async ({ request }) => {
          body = await request.json();
          return HttpResponse.json({});
        }),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", {
          name: "Update statement for Family loan",
        }),
      );
      const dialog = await screen.findByRole("dialog");
      const balance = within(dialog).getByLabelText("Balance");
      await user.clear(balance);
      await user.type(balance, "248000");
      const asOf = within(dialog).getByLabelText("As of");
      await user.clear(asOf);
      await user.type(asOf, "2026-10-10");
      await user.click(
        within(dialog).getByRole("button", { name: "Save statement" }),
      );

      await waitFor(() =>
        expect(body).toEqual({ balance: 248000, as_of: "2026-10-10" }),
      );
    });

    it("closes a loan on the chosen date", async () => {
      serveHouse(withExamples([]));
      let body: unknown;
      server.use(
        http.post("/api/v1/house/loans/:id/close", async ({ request }) => {
          body = await request.json();
          return HttpResponse.json({});
        }),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", { name: "Close Family loan" }),
      );
      const dialog = await screen.findByRole("dialog");
      const closed = within(dialog).getByLabelText("Closed on");
      await user.clear(closed);
      await user.type(closed, "2026-10-12");
      await user.click(
        within(dialog).getByRole("button", { name: "Close loan" }),
      );

      await waitFor(() => expect(body).toEqual({ closed_on: "2026-10-12" }));
    });

    it("shows the server's message when a loan cannot be deleted", async () => {
      serveHouse(withExamples([]));
      server.use(
        http.delete("/api/v1/house/loans/:id", () =>
          HttpResponse.json(
            {
              error: {
                code: "VALIDATION_ERROR",
                message: "Loan has linked payments",
              },
            },
            { status: 422 },
          ),
        ),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", { name: "Delete Family loan" }),
      );
      const dialog = await screen.findByRole("dialog");
      await user.click(
        within(dialog).getByRole("button", { name: "Delete loan" }),
      );

      expect(await within(dialog).findByRole("alert")).toHaveTextContent(
        "Loan has linked payments",
      );
    });

    it("adds the next payments and says how many", async () => {
      serveHouse(withExamples([]));
      let body: unknown;
      server.use(
        http.post(
          "/api/v1/house/loans/:id/payment-obligations",
          async ({ request }) => {
            body = await request.json();
            return HttpResponse.json([{}, {}, {}, {}], { status: 201 });
          },
        ),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await screen.findByRole("heading", { name: "Loans" });
      await user.selectOptions(
        within(loansSection()).getByLabelText(/Payments to add/),
        "4",
      );
      await user.click(
        within(loansSection()).getByRole("button", {
          name: "Add next 4 payments for Family loan",
        }),
      );

      await waitFor(() => expect(body).toEqual({ months: 4 }));
      expect(await screen.findByText("Added 4 payments")).toBeInTheDocument();
    });

    it("says when there is nothing to add", async () => {
      serveHouse(withExamples([]));
      server.use(
        http.post("/api/v1/house/loans/:id/payment-obligations", () =>
          HttpResponse.json([], { status: 201 }),
        ),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", {
          name: "Add next 3 payments for Family loan",
        }),
      );
      expect(await screen.findByText("Nothing to add")).toBeInTheDocument();
    });
  });

  describe("upcoming obligations", () => {
    it("shows a status pill with text on every row", async () => {
      serveHouse(withExamples([]));
      renderWithProviders(<HousePage />);
      await screen.findByRole("heading", { name: "Upcoming" });
      const section = upcomingSection();

      const rows = within(section).getAllByRole("row");
      const late = rows.find((r) =>
        r.textContent?.includes("Family loan payment"),
      );
      expect(late).toHaveTextContent("Late");
      expect(within(late as HTMLElement).getByText("Late")).toHaveClass(
        "text-negative",
      );
      const tax = rows.find((r) => r.textContent?.includes("Property tax"));
      expect(tax).toHaveTextContent("Due");
      expect(within(section).getByText("Water bill")).toBeInTheDocument();
      expect(within(section).getByText("Paid")).toHaveClass("text-positive");
    });

    it("lists candidate rows and marks the chosen one paid", async () => {
      serveHouse(withExamples([]));
      let body: unknown;
      server.use(
        http.get("/api/v1/house/obligations/:id/candidates", () =>
          HttpResponse.json([
            {
              id: "tx-1",
              date: "2026-10-01",
              merchant: "Example Bank",
              account_name: "Joint checking",
              category: "Loan",
              amount: -937.5,
              payer_person_id: ALICE_ID,
              score: 5,
            },
            {
              id: "tx-2",
              date: "2026-10-03",
              merchant: "Other Lender",
              account_name: "Joint checking",
              category: "Loan",
              amount: -900,
              payer_person_id: null,
              score: 2,
            },
          ]),
        ),
        http.put(
          "/api/v1/house/obligations/:id/payment",
          async ({ request }) => {
            body = await request.json();
            return HttpResponse.json({});
          },
        ),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", {
          name: "Mark Family loan payment paid",
        }),
      );
      const dialog = await screen.findByRole("dialog");
      expect(
        await within(dialog).findByText("Other Lender"),
      ).toBeInTheDocument();
      const submit = within(dialog).getByRole("button", { name: "Mark paid" });
      expect(submit).toBeDisabled();
      await user.click(
        within(dialog).getByRole("radio", { name: /Example Bank/ }),
      );
      await user.click(submit);

      await waitFor(() => expect(body).toEqual({ transaction_id: "tx-1" }));
    });

    it("says so when no rows match", async () => {
      serveHouse(withExamples([]));
      server.use(
        http.get("/api/v1/house/obligations/:id/candidates", () =>
          HttpResponse.json([]),
        ),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", { name: "Mark Insurance paid" }),
      );
      const dialog = await screen.findByRole("dialog");
      expect(
        await within(dialog).findByText(
          "No matching rows found. Check that the payment was uploaded.",
        ),
      ).toBeInTheDocument();
    });

    it("shows the error, not an empty list, when candidates fail", async () => {
      serveHouse(withExamples([]));
      server.use(
        http.get("/api/v1/house/obligations/:id/candidates", () =>
          HttpResponse.json(
            { error: { code: "BOOM", message: "Candidate search failed" } },
            { status: 500 },
          ),
        ),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", { name: "Mark Insurance paid" }),
      );
      const dialog = await screen.findByRole("dialog");
      expect(
        await within(dialog).findByText("Candidate search failed"),
      ).toBeInTheDocument();
      expect(within(dialog).queryByText(/No matching rows/)).toBeNull();
    });

    it("hides row actions on example data", async () => {
      serveHouse(withExamples(["upcoming"]));
      renderWithProviders(<HousePage />);
      await screen.findByRole("heading", { name: "Upcoming" });
      const section = upcomingSection();

      expect(
        within(section).getByRole("button", { name: "Record an obligation" }),
      ).toBeInTheDocument();
      expect(
        within(section).queryByRole("button", { name: /^Mark / }),
      ).toBeNull();
      expect(
        within(section).queryByRole("button", { name: /^Edit / }),
      ).toBeNull();
      expect(
        within(section).queryByRole("button", { name: /^Delete / }),
      ).toBeNull();
      expect(
        within(section).queryByRole("button", { name: /^Unmark / }),
      ).toBeNull();
    });

    it("needs a loan before a loan payment can be recorded", async () => {
      serveHouse(withExamples([]));
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", { name: "Record an obligation" }),
      );
      const dialog = await screen.findByRole("dialog");
      await user.selectOptions(
        within(dialog).getByLabelText("Kind"),
        "loan_payment",
      );
      await user.type(within(dialog).getByLabelText("Description"), "Payment");
      await user.type(within(dialog).getByLabelText("Amount"), "100");
      await user.type(within(dialog).getByLabelText("Due"), "2026-12-01");
      const submit = within(dialog).getByRole("button", {
        name: "Record an obligation",
      });
      expect(submit).toBeDisabled();
      await user.selectOptions(within(dialog).getByLabelText("Loan"), "loan-1");
      expect(submit).toBeEnabled();
    });

    it("unmarks a paid obligation", async () => {
      serveHouse(withExamples([]));
      let body: unknown;
      server.use(
        http.put(
          "/api/v1/house/obligations/:id/payment",
          async ({ request }) => {
            body = await request.json();
            return HttpResponse.json({});
          },
        ),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", { name: "Unmark Water bill" }),
      );
      await waitFor(() => expect(body).toEqual({ transaction_id: null }));
    });

    it("records an obligation tied to a loan", async () => {
      serveHouse(withExamples([]));
      let body: unknown;
      server.use(
        http.post("/api/v1/house/obligations", async ({ request }) => {
          body = await request.json();
          return HttpResponse.json({}, { status: 201 });
        }),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", { name: "Record an obligation" }),
      );
      const dialog = await screen.findByRole("dialog");
      await user.selectOptions(
        within(dialog).getByLabelText("Kind"),
        "loan_payment",
      );
      await user.selectOptions(within(dialog).getByLabelText("Loan"), "loan-1");
      await user.type(
        within(dialog).getByLabelText("Description"),
        "December payment",
      );
      await user.type(within(dialog).getByLabelText("Amount"), "937.5");
      await user.type(within(dialog).getByLabelText("Due"), "2026-12-01");
      await user.type(
        within(dialog).getByLabelText(/Late after/),
        "2026-12-10",
      );
      await user.click(within(dialog).getByLabelText("Estimate"));
      await user.click(
        within(dialog).getByRole("button", { name: "Record an obligation" }),
      );

      await waitFor(() =>
        expect(body).toEqual({
          kind: "loan_payment",
          description: "December payment",
          amount: 937.5,
          is_estimate: true,
          due_on: "2026-12-01",
          late_after: "2026-12-10",
          pays_from: null,
          loan_id: "loan-1",
          notes: "",
        }),
      );
    });

    it("edits an obligation with a PUT", async () => {
      serveHouse(withExamples([]));
      let posted: { url: string; body: unknown } | undefined;
      server.use(
        http.put("/api/v1/house/obligations/:id", async ({ request }) => {
          posted = { url: request.url, body: await request.json() };
          return HttpResponse.json({});
        }),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", { name: "Edit Insurance" }),
      );
      const dialog = await screen.findByRole("dialog");
      const amount = within(dialog).getByLabelText("Amount");
      await user.clear(amount);
      await user.type(amount, "1500");
      await user.click(
        within(dialog).getByRole("button", { name: "Save obligation" }),
      );

      await waitFor(() => expect(posted).toBeDefined());
      expect(posted?.url).toContain("/obligations/ob-2");
      expect(posted?.body).toMatchObject({
        amount: 1500,
        due_on: "2027-01-15",
      });
    });

    it("deletes an obligation after confirming", async () => {
      serveHouse(withExamples([]));
      let deleted: string | undefined;
      server.use(
        http.delete("/api/v1/house/obligations/:id", ({ params }) => {
          deleted = params.id as string;
          return HttpResponse.json({ deleted: true });
        }),
      );
      const user = userEvent.setup();
      renderWithProviders(<HousePage />);

      await user.click(
        await screen.findByRole("button", { name: "Delete Insurance" }),
      );
      const dialog = await screen.findByRole("dialog");
      await user.click(
        within(dialog).getByRole("button", { name: "Delete obligation" }),
      );
      await waitFor(() => expect(deleted).toBe("ob-2"));
    });
  });
});
