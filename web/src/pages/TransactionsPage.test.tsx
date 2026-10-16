import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { TransactionResponse } from "@/api/generated/model";
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
import { TransactionsPage } from "./TransactionsPage";

function makeTx(overrides: Partial<TransactionResponse>): TransactionResponse {
  const tx: TransactionResponse = {
    id: "tx",
    date: "2026-01-15",
    merchant: "Generic Merchant",
    category: "Generic",
    account: "Chase",
    amount: -50,
    notes: "",
    tags: [],
    payer_person_id: "p1",
    payer_percentage: 50,
    household: true,
    is_excluded: false,
    is_settlement: false,
    is_transfer: false,
    is_income: false,
    original_date: null,
    original_amount: null,
    is_joint: false,
    account_id: "a1",
    shares: {},
    share_amounts: {},
    owner_shares: null,
    depositor_person_id: null,
    ...overrides,
  };
  // Mirror the server: per-person shares follow the payer split unless a
  // test pins them.
  if (!overrides.shares && tx.payer_person_id) {
    const other = tx.payer_person_id === "p1" ? "p2" : "p1";
    tx.shares = {
      [tx.payer_person_id]: tx.payer_percentage,
      [other]: 100 - tx.payer_percentage,
    };
  }
  // Mirror the server: the first owner (the payer of a personal row, p1 of a
  // joint row) takes the half-up cent; the other takes the remainder.
  if (!overrides.share_amounts) {
    const ids = Object.keys(tx.shares);
    const first =
      tx.is_joint || !tx.payer_person_id ? ids[0] : tx.payer_person_id;
    const second = ids.find((id) => id !== first);
    if (first && second) {
      const cents = Math.round(Math.abs(tx.amount) * 100);
      const firstCents = Math.floor(
        (cents * (tx.shares[first] ?? 0) + 50) / 100,
      );
      tx.share_amounts = {
        [first]: firstCents / 100,
        [second]: (cents - firstCents) / 100,
      };
    }
  }
  return tx;
}

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

const reconciliationResponse = {
  start_date: "2026-01-01",
  end_date: "2026-01-31",
  year: 2026,
  month: 1,
  is_finalized: false,
  finalized_at: null,
  total_household_spending: 160.0,
  total_household_refunds: 0.0,
  net_household_spending: 160.0,
  person_summaries: [
    { person_id: "p1", total_paid: 100.0, total_share: 80.0 },
    { person_id: "p2", total_paid: 60.0, total_share: 80.0 },
  ],
  settlement: { amount: 20.0, from_person_id: "p2", to_person_id: "p1" },
  category_group_breakdowns: [
    {
      group_id: "g1",
      group_name: "Food & Dining",
      total_amount: 160.0,
      transaction_count: 2,
      categories: [
        {
          category: "Dining Out",
          group_id: "g1",
          group_name: "Food & Dining",
          total_amount: 100.0,
          transaction_count: 1,
        },
        {
          category: "Groceries",
          group_id: "g1",
          group_name: "Food & Dining",
          total_amount: 60.0,
          transaction_count: 1,
        },
      ],
    },
  ],
  transaction_count: 2,
  transactions: [
    makeTx({
      id: "tx1",
      date: "2026-01-15",
      merchant: "Restaurant",
      category: "Dining Out",
      amount: -100,
      tags: ["shared"],
      payer_person_id: "p1",
    }),
    makeTx({
      id: "tx2",
      date: "2026-01-20",
      merchant: "Grocery Store",
      category: "Groceries",
      account: "Amex",
      amount: -60,
      tags: ["shared"],
      payer_person_id: "p2",
    }),
  ],
  upload_statuses: [
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
  ],
  unmapped_categories: [],
  latest_transaction_month: { year: 2026, month: 1 },
};

const emptyResponse = {
  start_date: "2026-03-01",
  end_date: "2026-03-31",
  year: 2026,
  month: 3,
  is_finalized: false,
  finalized_at: null,
  total_household_spending: 0.0,
  total_household_refunds: 0.0,
  net_household_spending: 0.0,
  person_summaries: [
    { person_id: "p1", total_paid: 0.0, total_share: 0.0 },
    { person_id: "p2", total_paid: 0.0, total_share: 0.0 },
  ],
  settlement: { amount: 0.0, from_person_id: "p1", to_person_id: "p2" },
  category_group_breakdowns: [],
  transaction_count: 0,
  transactions: [],
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
  unmapped_categories: [],
  latest_transaction_month: null,
};

// January's $20 in charges has no payments against it — carried forward in
// full, so the month's balance equals its charges.
const settleUpEmptyResponse = {
  year: 2026,
  month: 1,
  years: [
    {
      year: 2026,
      charged: { amount: 20.0, from_person_id: "p2", to_person_id: "p1" },
      paid: null,
      balance: { amount: 20.0, from_person_id: "p2", to_person_id: "p1" },
      span: { start: { year: 2026, month: 1 }, end: { year: 2026, month: 1 } },
    },
  ],
  months: [
    makeLedgerMonth({
      year: 2026,
      month: 1,
      charged: { amount: 20.0, from_person_id: "p2", to_person_id: "p1" },
      balance: { amount: 20.0, from_person_id: "p2", to_person_id: "p1" },
      status: "carried_forward",
    }),
  ],
  settlements: [],
  upload_statuses: reconciliationResponse.upload_statuses,
  persons: persons.map((p) => ({ id: p.id, name: p.name })),
  is_finalized: false,
  finalized_at: null,
  transaction_count: 2,
  latest_transaction_month: { year: 2026, month: 1 },
  finalization_warnings: [],
  payer_splits: [],
  payer_group_splits: [],
};

describe("TransactionsPage", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: "p1" });
    server.use(
      http.get("/api/v1/persons/", () => HttpResponse.json(persons)),
      http.get("/api/v1/reconciliation", () =>
        HttpResponse.json(reconciliationResponse),
      ),
      http.get("/api/v1/settle-up", () =>
        HttpResponse.json(settleUpEmptyResponse),
      ),
      http.get("/api/v1/category-groups", () => HttpResponse.json([])),
      http.get("/api/v1/tags", () => HttpResponse.json([])),
      http.get("/api/v1/persons/:personId/adjustments/:year/:month", () =>
        HttpResponse.json({
          adjustments: [],
          person_name: "Alice",
          adjustment_count: 0,
        }),
      ),
    );
  });

  it("renders the three header cards (Settlement, Imported, In view)", async () => {
    renderWithProviders(<TransactionsPage />);

    await waitFor(() => {
      // "Settlement" appears as both card label and filter chip; allow both.
      expect(screen.getAllByText("Settlement").length).toBeGreaterThanOrEqual(
        1,
      );
      expect(screen.getByText("Imported")).toBeInTheDocument();
      expect(screen.getByText("In view")).toBeInTheDocument();
    });
  });

  it("Settlement card shows the month's balance after payments, not its charges", async () => {
    // A $1,000 payment against January's $1,350.00 in charges leaves $350.00.
    server.use(
      http.get("/api/v1/settle-up", () =>
        HttpResponse.json({
          ...settleUpEmptyResponse,
          months: [
            makeLedgerMonth({
              year: 2026,
              month: 1,
              charged: {
                amount: 1350.0,
                from_person_id: "p1",
                to_person_id: "p2",
              },
              paid: {
                amount: 1000.0,
                from_person_id: "p1",
                to_person_id: "p2",
              },
              balance: {
                amount: 350.0,
                from_person_id: "p1",
                to_person_id: "p2",
              },
              status: "partially_settled",
            }),
          ],
          settlements: [
            makeLedgerSettlement({
              id: "s1",
              amount: 1000.0,
              from_person_id: "p1",
              to_person_id: "p2",
              method: "Venmo",
              settled_at: "2026-01-25T00:00:00Z",
              created_at: "2026-01-25T00:00:00Z",
              portions: [{ year: 2026, month: 1, amount: 1000.0 }],
            }),
          ],
        }),
      ),
    );
    renderWithProviders(<TransactionsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Alice owes Bob \$350\.00/)).toBeInTheDocument();
    });
    expect(
      screen.queryByText(/Alice owes Bob \$1,350\.00/),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/\$1,350\.00 charged · \$1,000\.00 paid/),
    ).toBeInTheDocument();
  });

  it("multi-month range never claims Settled — prompts to select a single month", async () => {
    renderWithProviders(<TransactionsPage />, {
      routerProps: {
        initialEntries: [
          "/transactions?startDate=2026-01-01&endDate=2026-02-28",
        ],
      },
    });

    await waitFor(() => {
      expect(
        screen.getByText("Select a single month to see settlement balance"),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText("Settled")).not.toBeInTheDocument();
  });

  it("does not claim Settled while the settle-up query is loading", async () => {
    server.use(
      http.get("/api/v1/settle-up", () => new Promise<never>(() => {})),
    );
    renderWithProviders(<TransactionsPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/2 transactions · \$160\.00 imported/),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText("Settled")).not.toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("renders the Imported card with tx count and total throughput", async () => {
    renderWithProviders(<TransactionsPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/2 transactions · \$160\.00 imported/),
      ).toBeInTheDocument();
    });
  });

  it("highlights settlement-linked rows with the HandCoins icon", async () => {
    server.use(
      http.get("/api/v1/reconciliation", () =>
        HttpResponse.json({
          ...reconciliationResponse,
          transaction_count: 3,
          transactions: [
            ...reconciliationResponse.transactions,
            makeTx({
              id: "tx-stl",
              date: "2026-01-25",
              merchant: "Venmo Transfer",
              category: "Cash & ATM",
              amount: -1000,
              tags: ["settlement"],
              payer_person_id: "p1",
              payer_percentage: 100,
              household: false,
              is_settlement: true,
            }),
          ],
        }),
      ),
    );
    renderWithProviders(<TransactionsPage />);

    await waitFor(() => {
      expect(screen.getByText("Venmo Transfer")).toBeInTheDocument();
    });
    expect(
      screen.getByLabelText("Linked settlement payment"),
    ).toBeInTheDocument();
  });

  it("Settlement quick-filter chip narrows the table to settlement rows", async () => {
    server.use(
      http.get("/api/v1/reconciliation", () =>
        HttpResponse.json({
          ...reconciliationResponse,
          transaction_count: 3,
          transactions: [
            ...reconciliationResponse.transactions,
            makeTx({
              id: "tx-stl",
              date: "2026-01-25",
              merchant: "Venmo Transfer",
              category: "Cash & ATM",
              amount: -1000,
              tags: ["settlement"],
              payer_person_id: "p1",
              payer_percentage: 100,
              household: false,
              is_settlement: true,
            }),
          ],
        }),
      ),
    );
    renderWithProviders(<TransactionsPage />);

    await waitFor(() => {
      expect(screen.getByText("Venmo Transfer")).toBeInTheDocument();
    });

    // The Settlement headline button is inside an <article> (Card); the chip
    // is in the filter row. Scope to the chip via its count badge text.
    const chip = screen
      .getAllByRole("button", { name: /Settlement/i })
      .find((el) => within(el).queryByText("1") !== null);
    if (!chip) throw new Error("Settlement filter chip not found");
    await userEvent.click(chip);

    await waitFor(() => {
      expect(screen.getByText("Venmo Transfer")).toBeInTheDocument();
      expect(screen.queryByText("Restaurant")).not.toBeInTheDocument();
      expect(screen.queryByText("Grocery Store")).not.toBeInTheDocument();
    });
  });

  it("renders transaction table rows", async () => {
    renderWithProviders(<TransactionsPage />);

    await waitFor(() => {
      expect(screen.getByText("Restaurant")).toBeInTheDocument();
      expect(screen.getByText("Grocery Store")).toBeInTheDocument();
    });
  });

  it("ignores malformed amount params instead of filtering everything out", async () => {
    renderWithProviders(<TransactionsPage />, {
      routerProps: { initialEntries: ["/transactions?minAmt=abc"] },
    });

    await waitFor(() => {
      expect(screen.getByText("Restaurant")).toBeInTheDocument();
      expect(screen.getByText("Grocery Store")).toBeInTheDocument();
    });
  });

  it("shows empty state when no transactions", async () => {
    server.use(
      http.get("/api/v1/reconciliation", () =>
        HttpResponse.json(emptyResponse),
      ),
    );

    renderWithProviders(<TransactionsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /No transactions for/ }),
      ).toBeInTheDocument();
    });
  });

  it("filters to transactions I spotted for my partner via the Spotted segment", async () => {
    const spottedDataset = {
      ...reconciliationResponse,
      transaction_count: 3,
      transactions: [
        ...reconciliationResponse.transactions,
        makeTx({
          id: "tx3",
          date: "2026-01-22",
          merchant: "Parking Ticket",
          category: "Parking & Tolls",
          amount: -45,
          tags: ["bob"],
          payer_person_id: "p1",
          payer_percentage: 0,
          household: false,
        }),
      ],
    };
    server.use(
      http.get("/api/v1/reconciliation", () =>
        HttpResponse.json(spottedDataset),
      ),
    );

    renderWithProviders(<TransactionsPage />);

    await waitFor(() => {
      expect(screen.getByText("Parking Ticket")).toBeInTheDocument();
    });

    const spottedSegment = screen.getByRole("radio", { name: /^Spotted/ });
    await userEvent.click(spottedSegment);

    await waitFor(() => {
      expect(screen.getByText("Parking Ticket")).toBeInTheDocument();
      expect(screen.queryByText("Restaurant")).not.toBeInTheDocument();
      expect(screen.queryByText("Grocery Store")).not.toBeInTheDocument();
    });

    expect(screen.getByText(/1 of 3 · Spotted/)).toBeInTheDocument();
  });

  it("badges transfer-category rows and keeps them out of the In view total", async () => {
    server.use(
      http.get("/api/v1/reconciliation", () =>
        HttpResponse.json({
          ...reconciliationResponse,
          transaction_count: 3,
          transactions: [
            ...reconciliationResponse.transactions,
            makeTx({
              id: "tx-cc",
              date: "2026-01-28",
              merchant: "Chase Card Payment",
              category: "Credit Card Payment",
              amount: -4000,
              payer_person_id: "p1",
              payer_percentage: 100,
              household: false,
              is_transfer: true,
            }),
          ],
        }),
      ),
    );
    renderWithProviders(<TransactionsPage />);

    await waitFor(() => {
      expect(screen.getByText("Chase Card Payment")).toBeInTheDocument();
    });
    expect(
      screen.getByTitle(/Transfer — money movement, not spending/),
    ).toBeInTheDocument();
    // In view sums spending only: $100 + $60, not the $4,000 payment.
    expect(screen.getByText("$160.00")).toBeInTheDocument();
    expect(
      screen.getByText(/3 transactions · \$4,160\.00 imported/),
    ).toBeInTheDocument();
  });

  describe("joint rows", () => {
    const jointRow = makeTx({
      id: "tx-joint",
      date: "2026-01-22",
      merchant: "Water Utility",
      category: "Utilities",
      account: "Joint Checking",
      amount: -80,
      payer_person_id: null,
      is_joint: true,
      payer_percentage: 100,
      shares: { p1: 50, p2: 50 },
    });
    const deposit = makeTx({
      id: "tx-dep",
      date: "2026-01-23",
      merchant: "Transfer In",
      category: "Deposit",
      account: "Joint Checking",
      amount: 500,
      payer_person_id: null,
      is_joint: true,
      shares: { p1: 50, p2: 50 },
      depositor_person_id: null,
    });

    function serveJoint() {
      server.use(
        http.get("/api/v1/reconciliation", () =>
          HttpResponse.json({
            ...reconciliationResponse,
            transaction_count: 4,
            transactions: [
              ...reconciliationResponse.transactions,
              jointRow,
              deposit,
            ],
          }),
        ),
      );
    }

    it("shows a Joint badge with the account instead of a payer", async () => {
      serveJoint();
      renderWithProviders(<TransactionsPage />);

      expect(await screen.findAllByText("Joint · Joint Checking")).toHaveLength(
        2,
      );
      expect(
        screen.getAllByTitle(
          "Joint account — outside settlement; shares by owner",
        ),
      ).toHaveLength(2);
    });

    it("offers owner shares, not the split editor, on a joint row", async () => {
      serveJoint();
      renderWithProviders(<TransactionsPage />);
      await userEvent.click(await screen.findByText("Water Utility"));

      expect(await screen.findByLabelText(/Alice/)).toHaveValue(50);
      expect(screen.getByLabelText(/Bob/)).toHaveValue(50);
      expect(
        screen.getByRole("button", { name: "Reset to 50/50" }),
      ).toBeInTheDocument();
      expect(document.getElementById("tx-split")).toBeNull();
      expect(screen.queryByText("Scope")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Depositor")).not.toBeInTheDocument();
    });

    it("keeps owner shares complementary and submits them", async () => {
      serveJoint();
      let body: unknown;
      server.use(
        http.patch("/api/v1/transactions/tx-joint", async ({ request }) => {
          body = await request.json();
          return HttpResponse.json(jointRow);
        }),
      );
      renderWithProviders(<TransactionsPage />);
      await userEvent.click(await screen.findByText("Water Utility"));

      const alice = await screen.findByLabelText(/Alice/);
      await userEvent.clear(alice);
      await userEvent.type(alice, "70");
      expect(screen.getByLabelText(/Bob/)).toHaveValue(30);

      await userEvent.click(
        screen.getByRole("button", { name: "Save Changes" }),
      );
      await waitFor(() =>
        expect(body).toEqual({ owner_shares: { p1: 70, p2: 30 } }),
      );
    });

    it("resets an override to 50/50 by sending null", async () => {
      server.use(
        http.get("/api/v1/reconciliation", () =>
          HttpResponse.json({
            ...reconciliationResponse,
            transaction_count: 3,
            transactions: [
              ...reconciliationResponse.transactions,
              {
                ...jointRow,
                owner_shares: { p1: 70, p2: 30 },
                shares: { p1: 70, p2: 30 },
              },
            ],
          }),
        ),
      );
      let body: unknown;
      server.use(
        http.patch("/api/v1/transactions/tx-joint", async ({ request }) => {
          body = await request.json();
          return HttpResponse.json(jointRow);
        }),
      );
      renderWithProviders(<TransactionsPage />);
      await userEvent.click(await screen.findByText("Water Utility"));
      await userEvent.click(
        screen.getByRole("button", { name: "Reset to 50/50" }),
      );
      await userEvent.click(
        screen.getByRole("button", { name: "Save Changes" }),
      );
      await waitFor(() => expect(body).toEqual({ owner_shares: null }));
    });

    it("picks a depositor on a joint credit", async () => {
      serveJoint();
      let body: unknown;
      server.use(
        http.patch("/api/v1/transactions/tx-dep", async ({ request }) => {
          body = await request.json();
          return HttpResponse.json(deposit);
        }),
      );
      renderWithProviders(<TransactionsPage />);
      await userEvent.click(await screen.findByText("Transfer In"));

      const select = screen.getByLabelText("Depositor");
      expect(select).toHaveValue("");
      await userEvent.selectOptions(select, "Bob");
      await userEvent.click(
        screen.getByRole("button", { name: "Save Changes" }),
      );
      await waitFor(() => expect(body).toEqual({ depositor_person_id: "p2" }));
    });

    it("counts unassigned deposits in a filter chip", async () => {
      serveJoint();
      renderWithProviders(<TransactionsPage />);
      const chip = await screen.findByRole("button", {
        name: /Unassigned deposits/,
      });
      expect(within(chip).getByText("1")).toBeInTheDocument();
      await userEvent.click(chip);

      await waitFor(() => {
        expect(screen.getByText("Transfer In")).toBeInTheDocument();
        expect(screen.queryByText("Water Utility")).not.toBeInTheDocument();
        expect(screen.queryByText("Restaurant")).not.toBeInTheDocument();
      });
    });

    it("hides owner-share bulk controls unless every selected row is joint", async () => {
      serveJoint();
      renderWithProviders(<TransactionsPage />);
      await screen.findByText("Water Utility");
      await userEvent.click(screen.getByRole("button", { name: "Bulk Edit" }));

      const rowCheckbox = (merchant: string) => {
        const row = screen.getByText(merchant).closest("tr");
        if (!row) throw new Error(`row for ${merchant} not found`);
        return within(row).getByRole("checkbox");
      };

      await userEvent.click(rowCheckbox("Water Utility"));
      expect(await screen.findByLabelText(/Alice/)).toBeInTheDocument();
      expect(document.getElementById("bulk-split")).toBeNull();

      await userEvent.click(rowCheckbox("Restaurant"));
      expect(screen.queryByLabelText(/Alice/)).not.toBeInTheDocument();
      expect(document.getElementById("bulk-split")).not.toBeNull();
    });
  });
});
