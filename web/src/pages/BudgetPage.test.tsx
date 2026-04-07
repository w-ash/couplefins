import { fireEvent } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { BudgetOverviewResponse } from "@/api/generated/model";
import { server } from "@/test/server";
import { renderWithProviders, screen, waitFor } from "@/test/test-utils";
import { BudgetPage } from "./BudgetPage";

const emptyOverview: BudgetOverviewResponse = {
  year: 2026,
  month: 3,
  group_statuses: [],
  total_monthly_budget: 0,
  total_monthly_spent: 0,
  total_ytd_budget: 0,
  total_ytd_spent: 0,
  budgets: [],
};

const overviewWithData: BudgetOverviewResponse = {
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
        {
          category: "Groceries",
          total_amount: 200,
          transaction_count: 5,
          include_personal: false,
          household_amount: 0,
          personal_amounts: [],
        },
        {
          category: "Dining Out",
          total_amount: 150,
          transaction_count: 3,
          include_personal: false,
          household_amount: 0,
          personal_amounts: [],
        },
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
      categories: [
        {
          category: "Gas",
          total_amount: 75,
          transaction_count: 2,
          include_personal: false,
          household_amount: 0,
          personal_amounts: [],
        },
      ],
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
      year: 2026,
      month: 1,
    },
  ],
};

describe("BudgetPage", () => {
  beforeEach(() => {
    server.use(
      http.get("/api/v1/budgets/overview", () =>
        HttpResponse.json(emptyOverview),
      ),
    );
  });

  it("renders the budget heading", () => {
    renderWithProviders(<BudgetPage />);
    expect(screen.getByRole("heading", { name: "Budget" })).toBeInTheDocument();
  });

  it("shows empty state when no budgets exist", async () => {
    renderWithProviders(<BudgetPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Add your first budget" }),
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
      // Text appears in both mobile and desktop layouts
      expect(screen.getAllByText("Food & Dining").length).toBeGreaterThan(0);
    });

    expect(screen.getAllByText("On track").length).toBeGreaterThan(0);
  });

  it("renders unbudgeted groups section", async () => {
    server.use(
      http.get("/api/v1/budgets/overview", () =>
        HttpResponse.json(overviewWithData),
      ),
    );

    renderWithProviders(<BudgetPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Auto & Transport").length).toBeGreaterThan(0);
    });

    expect(screen.getByText("Spending without a budget")).toBeInTheDocument();
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
    expect(screen.getByText("Year to date")).toBeInTheDocument();
  });

  it("has sort options", () => {
    renderWithProviders(<BudgetPage />);

    expect(screen.getByText("Urgency")).toBeInTheDocument();
    expect(screen.getByText("Spending")).toBeInTheDocument();
    expect(screen.getByText("Name")).toBeInTheDocument();
  });

  it("shows add budget button", async () => {
    server.use(
      http.get("/api/v1/budgets/overview", () =>
        HttpResponse.json(overviewWithData),
      ),
    );
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

  it("expands group to show categories", async () => {
    server.use(
      http.get("/api/v1/budgets/overview", () =>
        HttpResponse.json(overviewWithData),
      ),
    );

    renderWithProviders(<BudgetPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Food & Dining").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByLabelText("Expand Food & Dining"));

    expect(screen.getByText("Groceries")).toBeInTheDocument();
    expect(screen.getByText("Dining Out")).toBeInTheDocument();
  });

  it("shows delete dialog when clicking remove budget", async () => {
    server.use(
      http.get("/api/v1/budgets/overview", () =>
        HttpResponse.json(overviewWithData),
      ),
    );

    renderWithProviders(<BudgetPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Food & Dining").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByLabelText("Expand Food & Dining"));

    fireEvent.click(screen.getByText("Remove budget"));

    // Month comes from useMonthYear() (current date), not the response fixture
    const now = new Date();
    const monthNames = [
      "January",
      "February",
      "March",
      "April",
      "May",
      "June",
      "July",
      "August",
      "September",
      "October",
      "November",
      "December",
    ];
    const expected = `Remove Food & Dining budget for ${monthNames[now.getMonth()]} ${now.getFullYear()}?`;
    expect(screen.getByText(expected)).toBeInTheDocument();
    expect(
      screen.getByText("Monthly tracking for this group will stop."),
    ).toBeInTheDocument();
  });
});
