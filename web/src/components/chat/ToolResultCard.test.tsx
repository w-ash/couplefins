import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/test/test-utils";
import { ToolResultCard } from "./ToolResultCard";

describe("ToolResultCard", () => {
  it("returns null when result is undefined", () => {
    const { container } = renderWithProviders(
      <ToolResultCard toolCall={{ id: "1", name: "get_settlement_balance" }} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("returns null when isError is true", () => {
    const { container } = renderWithProviders(
      <ToolResultCard
        toolCall={{
          id: "1",
          name: "get_settlement_balance",
          result: { error: "oops" },
          isError: true,
        }}
      />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("returns null for unknown tool names", () => {
    const { container } = renderWithProviders(
      <ToolResultCard
        toolCall={{ id: "1", name: "unknown_tool", result: {} }}
      />,
    );
    expect(container.innerHTML).toBe("");
  });

  describe("SettlementCard", () => {
    it("renders from/to names and amount", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "get_settlement_balance",
            result: {
              month: "2026-03",
              is_finalized: false,
              remaining_balance: 147.5,
              from: "Alice",
              to: "Bob",
              gross_amount: 147.5,
              net_from: "Alice",
              net_to: "Bob",
              uploads: [],
            },
          }}
        />,
      );
      expect(screen.getByText(/Alice owes Bob/)).toBeInTheDocument();
      expect(screen.getByText("$147.50")).toBeInTheDocument();
      expect(screen.getByText("2026-03 settlement")).toBeInTheDocument();
    });

    it("leads with the remaining balance after a partial payment", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "get_settlement_balance",
            result: {
              month: "2026-03",
              is_finalized: false,
              remaining_balance: 47.5,
              from: "Alice",
              to: "Bob",
              gross_amount: 147.5,
              net_from: "Alice",
              net_to: "Bob",
              uploads: [],
            },
          }}
        />,
      );
      expect(screen.getByText(/Alice owes Bob/)).toBeInTheDocument();
      expect(screen.getByText("$47.50")).toBeInTheDocument();
      expect(screen.getByText(/before payments/)).toBeInTheDocument();
    });

    it("names the reversed debtor after an overpayment", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "get_settlement_balance",
            result: {
              month: "2026-03",
              is_finalized: false,
              remaining_balance: 10,
              from: "Alice",
              to: "Bob",
              gross_amount: 50,
              net_from: "Bob",
              net_to: "Alice",
              uploads: [],
            },
          }}
        />,
      );
      expect(screen.getByText(/Bob owes Alice/)).toBeInTheDocument();
      expect(screen.getByText("$10.00")).toBeInTheDocument();
      expect(screen.getByText(/Alice owed Bob/)).toBeInTheDocument();
    });

    it("shows settled state when the balance is fully paid", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "get_settlement_balance",
            result: {
              month: "2026-03",
              is_finalized: false,
              remaining_balance: 0,
              from: "Alice",
              to: "Bob",
              gross_amount: 147.5,
              uploads: [],
            },
          }}
        />,
      );
      expect(screen.getByText("All settled")).toBeInTheDocument();
      expect(screen.getByText(/Alice owed Bob/)).toBeInTheDocument();
    });

    it("renders status message when no owed amount", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "get_settlement_balance",
            result: {
              month: "2026-03",
              is_finalized: false,
              remaining_balance: 0,
              gross_amount: 0,
              status: "No settlement needed this month",
              uploads: [],
            },
          }}
        />,
      );
      expect(
        screen.getByText("No settlement needed this month"),
      ).toBeInTheDocument();
    });
  });

  describe("BudgetCard", () => {
    const budgetResult = {
      month: "2026-03",
      scope: "household",
      groups: [
        {
          name: "Food & Dining",
          spent: 742,
          budget: 800,
          health: "near_limit",
        },
        { name: "Travel", spent: 200, budget: 500, health: "on_track" },
        {
          name: "Shopping",
          spent: 350,
          budget: 300,
          health: "over_budget",
        },
      ],
      total_spent: 1292,
      total_budget: 1600,
      over_budget: ["Shopping"],
    };

    it("renders each group with spent/budget", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "get_budget_overview",
            result: budgetResult,
          }}
        />,
      );
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
      expect(screen.getByText("Travel")).toBeInTheDocument();
      expect(screen.getByText("Shopping")).toBeInTheDocument();
    });

    it("renders total row", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "get_budget_overview",
            result: budgetResult,
          }}
        />,
      );
      expect(screen.getByText("Total")).toBeInTheDocument();
      expect(screen.getByText(/\$1,292\.00/)).toBeInTheDocument();
    });

    it("renders scope label", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "get_budget_overview",
            result: budgetResult,
          }}
        />,
      );
      expect(screen.getByText("2026-03 household budget")).toBeInTheDocument();
    });
  });

  describe("TransactionTableCard", () => {
    const searchResult = {
      total_count: 25,
      showing: 2,
      transactions: [
        {
          date: "2026-03-15",
          merchant: "Whole Foods",
          amount: -83.42,
          category: "Groceries",
          payer: "Alice",
          split: "50/50",
          household: true,
        },
        {
          date: "2026-03-18",
          merchant: "Target",
          amount: -42.0,
          category: "Shopping",
          payer: "Bob",
          split: "70/30",
          household: true,
        },
      ],
    };

    it("renders table with correct columns", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "search_transactions",
            result: searchResult,
          }}
        />,
      );
      expect(screen.getByRole("table")).toBeInTheDocument();
      expect(screen.getByText("Date")).toBeInTheDocument();
      expect(screen.getByText("Merchant")).toBeInTheDocument();
      expect(screen.getByText("Amount")).toBeInTheDocument();
      expect(screen.getByText("Category")).toBeInTheDocument();
    });

    it("renders transaction data", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "search_transactions",
            result: searchResult,
          }}
        />,
      );
      expect(screen.getByText("Whole Foods")).toBeInTheDocument();
      expect(screen.getByText("Target")).toBeInTheDocument();
      expect(screen.getByText("Groceries")).toBeInTheDocument();
    });

    it("shows 'Showing N of M' when truncated", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "search_transactions",
            result: searchResult,
          }}
        />,
      );
      expect(
        screen.getByText("Showing 2 of 25 transactions"),
      ).toBeInTheDocument();
    });

    it("does not show truncation message when all shown", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "search_transactions",
            result: { ...searchResult, total_count: 2 },
          }}
        />,
      );
      expect(screen.queryByText(/Showing/)).not.toBeInTheDocument();
    });
  });

  describe("SpendingByGroupCard", () => {
    it("renders group table with total row", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "get_spending_by_group",
            result: {
              month: "2026-03",
              groups: [
                { name: "Food & Dining", spent: 742 },
                { name: "Travel", spent: 200 },
              ],
              total: 942,
            },
          }}
        />,
      );
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
      expect(screen.getByText("Travel")).toBeInTheDocument();
      expect(screen.getByText("Total")).toBeInTheDocument();
      expect(screen.getByText("$942.00")).toBeInTheDocument();
    });
  });

  describe("SpendingTrendsCard", () => {
    it("renders year and group count", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "get_spending_trends",
            result: {
              year: 2026,
              groups: [{ name: "Food" }, { name: "Travel" }, { name: "Auto" }],
            },
          }}
        />,
      );
      expect(
        screen.getByText("2026 trends across 3 category groups"),
      ).toBeInTheDocument();
    });
  });

  describe("DashboardStatusCard", () => {
    it("renders upload status for each person", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "get_dashboard_status",
            result: {
              month: "2026-03",
              uploads: [
                { person: "Alice", uploaded: true, count: 47 },
                { person: "Bob", uploaded: false, count: 0 },
              ],
              is_finalized: false,
              transaction_count: 47,
              finalization_warnings: [],
            },
          }}
        />,
      );
      expect(screen.getByText(/Alice.*47 transactions/)).toBeInTheDocument();
      expect(screen.getByText(/Bob.*not uploaded/)).toBeInTheDocument();
    });

    it("shows finalization status", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "get_dashboard_status",
            result: {
              month: "2026-03",
              uploads: [],
              is_finalized: true,
              transaction_count: 82,
              finalization_warnings: [],
            },
          }}
        />,
      );
      expect(
        screen.getByText("82 total transactions (finalized)"),
      ).toBeInTheDocument();
    });

    it("renders finalization warnings", () => {
      renderWithProviders(
        <ToolResultCard
          toolCall={{
            id: "1",
            name: "get_dashboard_status",
            result: {
              month: "2026-03",
              uploads: [],
              is_finalized: false,
              transaction_count: 82,
              finalization_warnings: ["3 unmapped categories"],
            },
          }}
        />,
      );
      expect(screen.getByText("3 unmapped categories")).toBeInTheDocument();
    });
  });
});
