import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { SpendingTrendsResponse } from "@/api/generated/model";
import { server } from "@/test/server";
import { renderWithProviders, screen, waitFor } from "@/test/test-utils";
import { InsightsPage } from "./InsightsPage";

const baseFields = {
  month: 2,
  comparison_cards: [] as SpendingTrendsResponse["comparison_cards"],
  budget_lines: [] as SpendingTrendsResponse["budget_lines"],
  settlement_trend: [] as SpendingTrendsResponse["settlement_trend"],
  comparison_monthly_group_spending:
    [] as SpendingTrendsResponse["comparison_monthly_group_spending"],
  persons: [
    { id: "p1", name: "Alice", adjustment_account: "" },
    { id: "p2", name: "Bob", adjustment_account: "" },
  ],
};

const emptyResponse: SpendingTrendsResponse = {
  year: 2026,
  monthly_group_spending: [],
  monthly_totals: [],
  group_summaries: [],
  ...baseFields,
};

const populatedResponse: SpendingTrendsResponse = {
  year: 2026,
  monthly_group_spending: [
    {
      year: 2026,
      month: 1,
      group_id: "g1",
      group_name: "Food & Dining",
      amount: 400,
      categories: [
        { category: "Dining Out", amount: 250 },
        { category: "Groceries", amount: 150 },
      ],
    },
    {
      year: 2026,
      month: 2,
      group_id: "g1",
      group_name: "Food & Dining",
      amount: 450,
      categories: [
        { category: "Dining Out", amount: 300 },
        { category: "Groceries", amount: 150 },
      ],
    },
    {
      year: 2026,
      month: 1,
      group_id: "g2",
      group_name: "Travel",
      amount: 300,
      categories: [{ category: "Flights", amount: 300 }],
    },
    {
      year: 2026,
      month: 2,
      group_id: "g2",
      group_name: "Travel",
      amount: 200,
      categories: [{ category: "Flights", amount: 200 }],
    },
  ],
  monthly_totals: [
    { year: 2026, month: 1, total_amount: 700 },
    { year: 2026, month: 2, total_amount: 650 },
  ],
  group_summaries: [
    {
      group_id: "g1",
      group_name: "Food & Dining",
      ytd_total: 850,
      transaction_count: 10,
    },
    {
      group_id: "g2",
      group_name: "Travel",
      ytd_total: 500,
      transaction_count: 5,
    },
  ],
  ...baseFields,
  comparison_cards: [
    {
      group_id: "g1",
      group_name: "Food & Dining",
      current_month_amount: 450,
      trailing_average: 400,
      delta_amount: 50,
      delta_percentage: 12.5,
    },
  ],
  budget_lines: [{ group_id: "g1", monthly_budget: 500 }],
  settlement_trend: [
    {
      year: 2026,
      month: 1,
      amount: 50,
      from_person_id: "p1",
      to_person_id: "p2",
      is_settled: true,
    },
    {
      year: 2026,
      month: 2,
      amount: 75,
      from_person_id: "p1",
      to_person_id: "p2",
      is_settled: false,
    },
  ],
};

describe("InsightsPage", () => {
  beforeEach(() => {
    server.use(
      http.get("/api/v1/insights/spending-trends", () =>
        HttpResponse.json(emptyResponse),
      ),
    );
  });

  it("renders the heading", () => {
    renderWithProviders(<InsightsPage />);
    expect(
      screen.getByRole("heading", { name: "Insights" }),
    ).toBeInTheDocument();
  });

  it("shows empty state when no data", async () => {
    renderWithProviders(<InsightsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "No spending data" }),
      ).toBeInTheDocument();
    });
  });

  it("renders sparkline cards for each group", async () => {
    server.use(
      http.get("/api/v1/insights/spending-trends", () =>
        HttpResponse.json(populatedResponse),
      ),
    );

    renderWithProviders(<InsightsPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Food & Dining").length).toBeGreaterThan(0);
    });
    expect(screen.getByText("Travel")).toBeInTheDocument();
    expect(screen.getByText("YTD: $850.00")).toBeInTheDocument();
    expect(screen.getByText("YTD: $500.00")).toBeInTheDocument();
  });

  it("shows KPI stats", async () => {
    server.use(
      http.get("/api/v1/insights/spending-trends", () =>
        HttpResponse.json(populatedResponse),
      ),
    );

    renderWithProviders(<InsightsPage />);

    await waitFor(() => {
      expect(screen.getByText("YTD shared spending")).toBeInTheDocument();
    });
    expect(screen.getByText("Monthly average")).toBeInTheDocument();
    expect(screen.getByText("Highest month")).toBeInTheDocument();
    expect(screen.getByText("Largest category")).toBeInTheDocument();
  });

  it("shows year selector", () => {
    renderWithProviders(<InsightsPage />);
    expect(screen.getByLabelText("Select year")).toBeInTheDocument();
  });

  it("shows month picker", () => {
    renderWithProviders(<InsightsPage />);
    expect(screen.getByLabelText("Select month")).toBeInTheDocument();
  });

  it("renders comparison cards", async () => {
    server.use(
      http.get("/api/v1/insights/spending-trends", () =>
        HttpResponse.json(populatedResponse),
      ),
    );

    renderWithProviders(<InsightsPage />);

    await waitFor(() => {
      expect(screen.getByText("3-mo avg: $400.00")).toBeInTheDocument();
    });
  });

  it("renders settlement trend heading", async () => {
    server.use(
      http.get("/api/v1/insights/spending-trends", () =>
        HttpResponse.json(populatedResponse),
      ),
    );

    renderWithProviders(<InsightsPage />);

    await waitFor(() => {
      expect(screen.getByText("Settlement Balance")).toBeInTheDocument();
    });
  });

  it("hides comparison cards when empty", async () => {
    const noComparisons = {
      ...populatedResponse,
      comparison_cards: [],
    };
    server.use(
      http.get("/api/v1/insights/spending-trends", () =>
        HttpResponse.json(noComparisons),
      ),
    );

    renderWithProviders(<InsightsPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Food & Dining").length).toBeGreaterThan(0);
    });
    expect(screen.queryByText("vs 3-month average")).not.toBeInTheDocument();
  });

  it("shows error state", async () => {
    server.use(
      http.get("/api/v1/insights/spending-trends", () =>
        HttpResponse.json(
          { error: { code: "SERVER_ERROR", message: "Something broke" } },
          { status: 500 },
        ),
      ),
    );

    renderWithProviders(<InsightsPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("renders YoY toggle", () => {
    renderWithProviders(<InsightsPage />);
    expect(screen.getByText("This year")).toBeInTheDocument();
    expect(screen.getByText("vs Last year")).toBeInTheDocument();
  });

  it("expands sparkline card on click", async () => {
    server.use(
      http.get("/api/v1/insights/spending-trends", () =>
        HttpResponse.json(populatedResponse),
      ),
    );

    renderWithProviders(<InsightsPage />, {
      routerProps: { initialEntries: ["/?year=2026&month=2"] },
    });

    await waitFor(() => {
      expect(screen.getAllByText("Food & Dining").length).toBeGreaterThan(0);
    });

    // Sparkline cards should have expand buttons
    const expandButtons = screen.getAllByRole("button", { expanded: false });
    const sparklineButton = expandButtons.find((btn) =>
      btn.textContent?.includes("Food & Dining"),
    );
    expect(sparklineButton).toBeDefined();

    // Click to expand
    sparklineButton?.click();

    // Should show category breakdown for month 2
    await waitFor(() => {
      expect(screen.getByText("Dining Out")).toBeInTheDocument();
    });
    expect(screen.getByText("Groceries")).toBeInTheDocument();
    expect(screen.getByText("View transactions")).toBeInTheDocument();
  });
});
