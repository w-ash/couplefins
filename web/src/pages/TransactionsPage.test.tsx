import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
} from "vitest";
import { useIdentityStore } from "@/lib/identity";
import { renderWithProviders, screen, waitFor } from "../test/test-utils";
import { TransactionsPage } from "./TransactionsPage";

const persons = [
  { id: "p1", name: "Alice", adjustment_account: "" },
  { id: "p2", name: "Bob", adjustment_account: "" },
];

const reconciliationResponse = {
  year: 2026,
  month: 1,
  total_shared_spending: 160.0,
  total_shared_refunds: 0.0,
  net_shared_spending: 160.0,
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
    {
      id: "tx1",
      date: "2026-01-15",
      merchant: "Restaurant",
      category: "Dining Out",
      account: "Chase",
      amount: -100.0,
      payer_person_id: "p1",
      payer_percentage: 50,
    },
    {
      id: "tx2",
      date: "2026-01-20",
      merchant: "Grocery Store",
      category: "Groceries",
      account: "Amex",
      amount: -60.0,
      payer_person_id: "p2",
      payer_percentage: 50,
    },
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
};

const emptyResponse = {
  year: 2026,
  month: 3,
  total_shared_spending: 0.0,
  total_shared_refunds: 0.0,
  net_shared_spending: 0.0,
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
};

const server = setupServer(
  http.get("/api/v1/persons/", () => HttpResponse.json(persons)),
  http.get("/api/v1/reconciliation", () =>
    HttpResponse.json(reconciliationResponse),
  ),
  http.get("/api/v1/persons/:personId/adjustments/:year/:month", () =>
    HttpResponse.json({
      adjustments: [],
      person_name: "Alice",
      adjustment_count: 0,
    }),
  ),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("TransactionsPage", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: "p1" });
  });

  it("renders settlement card with amount", async () => {
    renderWithProviders(<TransactionsPage />);

    await waitFor(() => {
      expect(screen.getByText(/owes/)).toBeInTheDocument();
      expect(screen.getByText("$20.00")).toBeInTheDocument();
    });
  });

  it("renders transaction table rows", async () => {
    renderWithProviders(<TransactionsPage />);

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
        screen.getByText(/No shared transactions for/),
      ).toBeInTheDocument();
    });
  });

  it("shows partial upload banner", async () => {
    const partialResponse = {
      ...reconciliationResponse,
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
          has_uploaded: false,
          upload_count: 0,
        },
      ],
    };
    server.use(
      http.get("/api/v1/reconciliation", () =>
        HttpResponse.json(partialResponse),
      ),
    );

    renderWithProviders(<TransactionsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Bob hasn't uploaded yet/)).toBeInTheDocument();
    });
  });
});
