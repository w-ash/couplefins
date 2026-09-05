import { describe, expect, it } from "vitest";
import { buildTransactionsUrl } from "./transaction-links";

describe("buildTransactionsUrl", () => {
  it("emits a month range with the params in a stable order", () => {
    expect(
      buildTransactionsUrl({
        range: { year: 2026, month: 3 },
        scope: "household",
        payerId: "p1",
        categoryNames: ["Dining Out", "Groceries & Home Supplies"],
        settlement: true,
      }),
    ).toBe(
      "/transactions?year=2026&month=3&scope=household&payer=p1&cat=Dining+Out&cat=Groceries+%26+Home+Supplies&settlement=1",
    );
  });

  it("emits an explicit date range for year to date", () => {
    expect(
      buildTransactionsUrl({
        range: { startDate: "2026-01-01", endDate: "2026-03-31" },
        scope: "personal",
      }),
    ).toBe(
      "/transactions?startDate=2026-01-01&endDate=2026-03-31&scope=personal",
    );
  });

  it("omits the scope for all, and unset filters", () => {
    expect(
      buildTransactionsUrl({ range: { year: 2026, month: 1 }, scope: "all" }),
    ).toBe("/transactions?year=2026&month=1");
  });

  it("carries a merchant search as q", () => {
    expect(
      buildTransactionsUrl({
        range: { year: 2026, month: 1 },
        query: "Sushi Place",
      }),
    ).toBe("/transactions?year=2026&month=1&q=Sushi+Place");
  });
});
