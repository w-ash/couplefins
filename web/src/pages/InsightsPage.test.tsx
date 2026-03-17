import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { SpendingTrendsResponse } from "@/api/generated/model";
import { server } from "@/test/server";
import { renderWithProviders, screen, waitFor } from "@/test/test-utils";
import { InsightsPage } from "./InsightsPage";

const emptyResponse: SpendingTrendsResponse = {
  year: 2026,
  monthly_group_spending: [],
  monthly_totals: [],
  group_summaries: [],
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
    },
    {
      year: 2026,
      month: 2,
      group_id: "g1",
      group_name: "Food & Dining",
      amount: 450,
    },
    { year: 2026, month: 1, group_id: "g2", group_name: "Travel", amount: 300 },
    { year: 2026, month: 2, group_id: "g2", group_name: "Travel", amount: 200 },
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
    // Verify YTD totals are shown on the sparkline cards
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
});
