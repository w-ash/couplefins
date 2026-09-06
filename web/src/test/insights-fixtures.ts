import type {
  SpendingFlowCellItem,
  SpendingFlowItem,
  SpendingTrendsResponse,
} from "@/api/generated/model";
import type { FlowContext } from "@/lib/spending-flow";

export const ALICE = { id: "p1", name: "Alice" };
export const BOB = { id: "p2", name: "Bob" };

export const PERSONS: SpendingTrendsResponse["persons"] = [
  {
    id: ALICE.id,
    name: ALICE.name,
    adjustment_account: "",
    theme_preference: "system",
    chat_voice: "fiona",
  },
  {
    id: BOB.id,
    name: BOB.name,
    adjustment_account: "",
    theme_preference: "system",
    chat_voice: "fiona",
  },
];

export function cell(
  overrides: Partial<SpendingFlowCellItem> = {},
): SpendingFlowCellItem {
  return {
    source_kind: "payer",
    source_person_id: ALICE.id,
    group_id: "g1",
    group_name: "Food & Dining",
    category: "Dining Out",
    amount: 100,
    transaction_count: 2,
    ...overrides,
  };
}

export function emptyFlow(): SpendingFlowItem {
  return { cells: [], top_merchants: [] };
}

/** February 2026, two groups, both partners paying. */
export const MONTH_FLOW: SpendingFlowItem = {
  cells: [
    cell({ category: "Dining Out", amount: 200, transaction_count: 4 }),
    cell({
      category: "Dining Out",
      amount: 100,
      transaction_count: 2,
      source_person_id: BOB.id,
    }),
    cell({ category: "Groceries", amount: 150, transaction_count: 3 }),
    cell({
      group_id: "g2",
      group_name: "Travel",
      category: "Flights",
      amount: 200,
      transaction_count: 1,
    }),
  ],
  top_merchants: [
    {
      merchant: "Airline",
      amount: 200,
      transaction_count: 1,
      category: "Flights",
      group_id: "g2",
    },
    {
      merchant: "Sushi Place",
      amount: 180,
      transaction_count: 3,
      category: "Dining Out",
      group_id: "g1",
    },
  ],
};

export const YTD_FLOW: SpendingFlowItem = {
  cells: [
    cell({ category: "Dining Out", amount: 450, transaction_count: 8 }),
    cell({
      category: "Dining Out",
      amount: 100,
      transaction_count: 2,
      source_person_id: BOB.id,
    }),
    cell({ category: "Groceries", amount: 300, transaction_count: 6 }),
    cell({
      group_id: "g2",
      group_name: "Travel",
      category: "Flights",
      amount: 500,
      transaction_count: 2,
    }),
  ],
  top_merchants: [
    {
      merchant: "Airline",
      amount: 500,
      transaction_count: 2,
      category: "Flights",
      group_id: "g2",
    },
  ],
};

export function makeSpendingTrends(
  overrides: Partial<SpendingTrendsResponse> = {},
): SpendingTrendsResponse {
  return {
    year: 2026,
    month: 2,
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
      {
        year: 2026,
        month: 1,
        group_id: "g2",
        group_name: "Travel",
        amount: 300,
      },
      {
        year: 2026,
        month: 2,
        group_id: "g2",
        group_name: "Travel",
        amount: 200,
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
        transaction_count: 16,
      },
      {
        group_id: "g2",
        group_name: "Travel",
        ytd_total: 500,
        transaction_count: 2,
      },
    ],
    comparison_cards: [
      {
        group_id: "g1",
        group_name: "Food & Dining",
        current_month_amount: 450,
        trailing_average: 400,
        delta_amount: 50,
        delta_percentage: 12.5,
        is_new: false,
      },
      {
        group_id: "g2",
        group_name: "Travel",
        current_month_amount: 200,
        trailing_average: 300,
        delta_amount: -100,
        delta_percentage: -33.3,
        is_new: false,
      },
    ],
    category_comparisons: [
      {
        category: "Dining Out",
        group_id: "g1",
        group_name: "Food & Dining",
        current_month_amount: 300,
        trailing_average: 250,
        delta_amount: 50,
        delta_percentage: 20,
        is_new: false,
      },
      {
        category: "Flights",
        group_id: "g2",
        group_name: "Travel",
        current_month_amount: 200,
        trailing_average: 300,
        delta_amount: -100,
        delta_percentage: -33.3,
        is_new: false,
      },
      {
        category: "Groceries",
        group_id: "g1",
        group_name: "Food & Dining",
        current_month_amount: 150,
        trailing_average: 0,
        delta_amount: 150,
        delta_percentage: 0,
        is_new: true,
      },
    ],
    month_flow: MONTH_FLOW,
    ytd_flow: YTD_FLOW,
    persons: PERSONS,
    comparison_monthly_group_spending: [
      {
        year: 2025,
        month: 1,
        group_id: "g1",
        group_name: "Food & Dining",
        amount: 380,
      },
      {
        year: 2025,
        month: 2,
        group_id: "g1",
        group_name: "Food & Dining",
        amount: 420,
      },
      {
        year: 2025,
        month: 12,
        group_id: "g1",
        group_name: "Food & Dining",
        amount: 500,
      },
    ],
    ...overrides,
  };
}

export function makeEmptySpendingTrends(): SpendingTrendsResponse {
  return makeSpendingTrends({
    monthly_group_spending: [],
    monthly_totals: [],
    group_summaries: [],
    comparison_cards: [],
    category_comparisons: [],
    month_flow: emptyFlow(),
    ytd_flow: emptyFlow(),
    comparison_monthly_group_spending: [],
  });
}

export function makeFlowContext(
  overrides: Partial<FlowContext> = {},
): FlowContext {
  return {
    range: { year: 2026, month: 2 },
    scope: "household",
    currentPersonId: ALICE.id,
    personNames: new Map([
      [ALICE.id, ALICE.name],
      [BOB.id, BOB.name],
    ]),
    personIndex: new Map([
      [ALICE.id, 0],
      [BOB.id, 1],
    ]),
    groupColors: new Map([
      ["g1", "var(--chart-0)"],
      ["g2", "var(--chart-1)"],
    ]),
    ...overrides,
  };
}
