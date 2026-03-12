import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import type { BudgetOverviewData } from "@/lib/budgets";
import { renderWithProviders, screen, waitFor } from "@/test/test-utils";
import { BudgetPage } from "./BudgetPage";

const emptyOverview: BudgetOverviewData = {
  year: 2026,
  month: 3,
  group_statuses: [],
  total_monthly_budget: 0,
  total_monthly_spent: 0,
  total_ytd_budget: 0,
  total_ytd_spent: 0,
  budgets: [],
};

const overviewWithData: BudgetOverviewData = {
  year: 2026,
  month: 3,
  group_statuses: [
    {
      group_id: "g1",
      group_name: "Food & Dining",
      budget_id: "b1",
      monthly_budget: 500,
      monthly_spent: 350,
      ytd_budget: 1500,
      ytd_spent: 1100,
      monthly_health: "on_track",
      ytd_health: "near_limit",
      average_monthly_spending: 366.67,
      categories: [
        { category: "Groceries", total_amount: 200, transaction_count: 5 },
        { category: "Dining Out", total_amount: 150, transaction_count: 3 },
      ],
    },
    {
      group_id: "g2",
      group_name: "Auto & Transport",
      budget_id: null,
      monthly_budget: null,
      monthly_spent: 75,
      ytd_budget: null,
      ytd_spent: 200,
      monthly_health: null,
      ytd_health: null,
      average_monthly_spending: 66.67,
      categories: [{ category: "Gas", total_amount: 75, transaction_count: 2 }],
    },
  ],
  total_monthly_budget: 500,
  total_monthly_spent: 350,
  total_ytd_budget: 1500,
  total_ytd_spent: 1100,
  budgets: [
    {
      id: "b1",
      group_id: "g1",
      monthly_amount: 500,
      effective_from: "2026-01-01",
    },
  ],
};

const server = setupServer(
  http.get("/api/v1/budgets/overview", () => HttpResponse.json(emptyOverview)),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("BudgetPage", () => {
  it("renders the budget heading", () => {
    renderWithProviders(<BudgetPage />);
    expect(screen.getByRole("heading", { name: "Budget" })).toBeInTheDocument();
  });

  it("shows empty state when no budgets exist", async () => {
    renderWithProviders(<BudgetPage />);

    await waitFor(() => {
      expect(
        screen.getByText(
          "No budgets set. Add a budget to start tracking shared spending.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders budgeted groups with health indicator", async () => {
    server.use(
      http.get("/api/v1/budgets/overview", () =>
        HttpResponse.json(overviewWithData),
      ),
    );

    renderWithProviders(<BudgetPage />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });

    expect(screen.getByText("On track")).toBeInTheDocument();
  });

  it("renders unbudgeted groups section", async () => {
    server.use(
      http.get("/api/v1/budgets/overview", () =>
        HttpResponse.json(overviewWithData),
      ),
    );

    renderWithProviders(<BudgetPage />);

    await waitFor(() => {
      expect(screen.getByText("Auto & Transport")).toBeInTheDocument();
    });

    expect(screen.getByText("Unbudgeted spending")).toBeInTheDocument();
  });

  it("renders summary stats", async () => {
    server.use(
      http.get("/api/v1/budgets/overview", () =>
        HttpResponse.json(overviewWithData),
      ),
    );

    renderWithProviders(<BudgetPage />);

    await waitFor(() => {
      expect(screen.getByText("Total budget")).toBeInTheDocument();
    });

    expect(screen.getByText("Total spent")).toBeInTheDocument();
    expect(screen.getByText("Remaining")).toBeInTheDocument();
  });

  it("has monthly/ytd toggle", () => {
    renderWithProviders(<BudgetPage />);

    expect(screen.getByText("Monthly")).toBeInTheDocument();
    expect(screen.getByText("YTD")).toBeInTheDocument();
  });

  it("has sort selector", () => {
    renderWithProviders(<BudgetPage />);

    expect(screen.getByLabelText("Sort order")).toBeInTheDocument();
  });

  it("shows add budget button", async () => {
    renderWithProviders(<BudgetPage />);

    await waitFor(() => {
      expect(screen.getByText("Add budget")).toBeInTheDocument();
    });
  });

  it("shows error state", async () => {
    server.use(
      http.get("/api/v1/budgets/overview", () =>
        HttpResponse.json(
          { error: { code: "SERVER_ERROR", message: "Something broke" } },
          { status: 500 },
        ),
      ),
    );

    renderWithProviders(<BudgetPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
