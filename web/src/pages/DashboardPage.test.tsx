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
import { DashboardPage } from "./DashboardPage";

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

const dashboardResponse = {
  scope: "household",
  current_person_id: null,
  current_month_year: 2026,
  current_month_month: 1,
  current_month_total_household_spending: 160.0,
  current_month_net_household_spending: 160.0,
  current_month_transaction_count: 2,
  current_month_person_summaries: [
    { person_id: "p1", total_paid: 100.0, total_share: 80.0 },
    { person_id: "p2", total_paid: 60.0, total_share: 80.0 },
  ],
  current_month_settlement: {
    amount: 20.0,
    from_person_id: "p2",
    to_person_id: "p1",
  },
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
  household_spending_month: 160.0,
  household_spending_ytd: 160.0,
  ytd_settlement: {
    amount: 20.0,
    from_person_id: "p2",
    to_person_id: "p1",
  },
  ytd_total_settled: 20.0,
  month_history: [
    {
      year: 2026,
      month: 1,
      total_household_spending: 160.0,
      settlement_amount: 20.0,
      settlement_from_person_id: "p2",
      settlement_to_person_id: "p1",
      is_finalized: false,
      is_settled: true,
      settled_at: "2026-02-01T12:00:00Z",
    },
  ],
  persons: [
    { id: "p1", name: "Alice" },
    { id: "p2", name: "Bob" },
  ],
  unmapped_categories: [],
  is_finalized: false,
  finalized_at: null,
};

const emptyResponse = {
  scope: "household",
  current_person_id: null,
  current_month_year: 2026,
  current_month_month: 3,
  current_month_total_household_spending: 0.0,
  current_month_net_household_spending: 0.0,
  current_month_transaction_count: 0,
  current_month_person_summaries: [
    { person_id: "p1", total_paid: 0.0, total_share: 0.0 },
    { person_id: "p2", total_paid: 0.0, total_share: 0.0 },
  ],
  current_month_settlement: {
    amount: 0.0,
    from_person_id: "p1",
    to_person_id: "p2",
  },
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
  household_spending_month: 0.0,
  household_spending_ytd: 0.0,
  ytd_settlement: null,
  ytd_total_settled: 0,
  month_history: [],
  persons: [
    { id: "p1", name: "Alice" },
    { id: "p2", name: "Bob" },
  ],
  unmapped_categories: [],
  is_finalized: false,
  finalized_at: null,
};

describe("DashboardPage", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: "p1" });
    server.use(
      http.get("/api/v1/persons/", () => HttpResponse.json(persons)),
      http.get("/api/v1/dashboard", () => HttpResponse.json(dashboardResponse)),
    );
  });

  it("renders settlement card with amount", async () => {
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      const owesElements = screen.getAllByText(/owes/);
      expect(owesElements.length).toBeGreaterThanOrEqual(1);
      const amountElements = screen.getAllByText("$20.00");
      expect(amountElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows upload status indicators", async () => {
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText("uploaded")).toHaveLength(2);
    });
  });

  it("shows empty state when no data", async () => {
    server.use(
      http.get("/api/v1/dashboard", () => HttpResponse.json(emptyResponse)),
    );

    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/No data for/)).toBeInTheDocument();
      expect(screen.getByText("Upload CSV")).toBeInTheDocument();
    });
  });

  it("renders month history rows", async () => {
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Month History")).toBeInTheDocument();
      expect(screen.getAllByText("January 2026").length).toBeGreaterThanOrEqual(
        1,
      );
    });
  });

  it("shows household summary stats", async () => {
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Household spending")).toBeInTheDocument();
      expect(screen.getByText("Household YTD")).toBeInTheDocument();
      expect(screen.getByText("YTD balance")).toBeInTheDocument();
      expect(screen.getByText("Settled this year")).toBeInTheDocument();
    });
  });

  it("shows partial upload status when only one person uploaded", async () => {
    const partialResponse = {
      ...dashboardResponse,
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
      http.get("/api/v1/dashboard", () => HttpResponse.json(partialResponse)),
    );

    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("uploaded")).toBeInTheDocument();
      expect(screen.getByText("not yet")).toBeInTheDocument();
    });
  });

  it("month history rows link to transactions page", async () => {
    const user = userEvent.setup();
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Month History")).toBeInTheDocument();
    });

    const table = screen.getByText("Month History").closest("div");
    if (!table) throw new Error("Expected history container to exist");
    const row = within(table).getByText("January 2026").closest("tr");
    if (!row) throw new Error("Expected row to exist");
    await user.click(row);

    expect(row).toHaveClass("cursor-pointer");
  });

  it("shows unsettled month with pending indicator text", async () => {
    const unsettledResponse = {
      ...dashboardResponse,
      month_history: [
        {
          ...dashboardResponse.month_history[0],
          is_settled: false,
          settled_at: null,
        },
      ],
    };
    server.use(
      http.get("/api/v1/dashboard", () => HttpResponse.json(unsettledResponse)),
    );

    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      const table = screen.getByText("Month History").closest("div");
      if (!table) throw new Error("Expected history container");
      expect(within(table).getByText(/owes/)).toBeInTheDocument();
    });
  });

  it("shows scope toggle with three options", async () => {
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Household")).toBeInTheDocument();
      expect(screen.getByText("My Spending")).toBeInTheDocument();
      expect(screen.getByText("All")).toBeInTheDocument();
    });
  });

  it("shows personal stats when scope is personal", async () => {
    const personalResponse = {
      ...dashboardResponse,
      scope: "personal",
      current_person_id: "p1",
      my_spending_month: 95.0,
      my_household_share_month: 80.0,
      my_personal_spending_month: 15.0,
      my_spending_ytd: 95.0,
      personal_month_history: [
        {
          year: 2026,
          month: 1,
          total_spending: 95.0,
          household_portion: 80.0,
          own_spending: 15.0,
        },
      ],
      budget_alerts: [],
      upload_statuses: [
        {
          person_id: "p1",
          person_name: "Alice",
          has_uploaded: true,
          upload_count: 1,
        },
      ],
    };
    server.use(
      http.get("/api/v1/dashboard", () => HttpResponse.json(personalResponse)),
    );

    renderWithProviders(<DashboardPage />);

    // Click "My Spending" tab
    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByText("Household")).toBeInTheDocument();
    });
    await user.click(screen.getByText("My Spending"));

    await waitFor(() => {
      expect(screen.getByText("My spending")).toBeInTheDocument();
      expect(screen.getByText("Household share")).toBeInTheDocument();
      expect(screen.getByText("Personal only")).toBeInTheDocument();
    });
  });

  it("shows budget alerts in personal scope", async () => {
    const personalResponse = {
      ...dashboardResponse,
      scope: "personal",
      current_person_id: "p1",
      my_spending_month: 95.0,
      my_household_share_month: 80.0,
      my_personal_spending_month: 15.0,
      my_spending_ytd: 95.0,
      personal_month_history: [],
      budget_alerts: [
        {
          group_id: "g1",
          group_name: "Food & Dining",
          monthly_budget: 200.0,
          monthly_spent: 185.0,
          health: "near_limit",
        },
      ],
      upload_statuses: [
        {
          person_id: "p1",
          person_name: "Alice",
          has_uploaded: true,
          upload_count: 1,
        },
      ],
    };
    server.use(
      http.get("/api/v1/dashboard", () => HttpResponse.json(personalResponse)),
    );

    renderWithProviders(<DashboardPage />);

    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByText("Household")).toBeInTheDocument();
    });
    await user.click(screen.getByText("My Spending"));

    await waitFor(() => {
      expect(screen.getByText("Budget alerts")).toBeInTheDocument();
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });
  });
});
