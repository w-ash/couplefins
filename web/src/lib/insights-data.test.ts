import { describe, expect, it } from "vitest";
import { makeFlowContext, makeSpendingTrends } from "@/test/insights-fixtures";
import {
  buildGroupRows,
  buildHeadline,
  buildMonthlyStack,
  buildNotable,
  detectCreep,
  periodLabel,
} from "./insights-data";

const ctx = makeFlowContext();
const data = makeSpendingTrends();

describe("periodLabel", () => {
  it("names a month or a year-to-date span", () => {
    expect(periodLabel(2026, 3, "month")).toBe("March 2026");
    expect(periodLabel(2026, 3, "ytd")).toBe("Jan–Mar 2026");
    expect(periodLabel(2026, 1, "ytd")).toBe("January 2026");
  });
});

describe("buildHeadline", () => {
  it("compares the month with the previous month", () => {
    const h = buildHeadline(data, "month");
    expect(h).toEqual({
      label: "February 2026",
      total: 650,
      comparison: {
        text: "less than January",
        deltaPct: ((650 - 700) / 700) * 100,
        deltaAmount: -50,
      },
    });
  });

  it("compares January with the prior December", () => {
    const h = buildHeadline({ ...data, month: 1 }, "month");
    expect(h.comparison).toEqual({
      text: "more than December 2025",
      deltaPct: ((700 - 500) / 500) * 100,
      deltaAmount: 200,
    });
  });

  it("compares year to date with the same span last year", () => {
    const h = buildHeadline(data, "ytd");
    expect(h.label).toBe("Jan–Feb 2026");
    expect(h.total).toBe(1350);
    expect(h.comparison?.text).toBe("more than Jan–Feb 2025");
  });

  it("has no comparison when nothing came before", () => {
    const h = buildHeadline(
      { ...data, month: 1, comparison_monthly_group_spending: [] },
      "month",
    );
    expect(h.comparison).toBeNull();
  });
});

describe("buildMonthlyStack", () => {
  it("lays out twelve months with a column per group and the prior year", () => {
    const { series, rows } = buildMonthlyStack(data, ctx);
    expect(series.map((s) => [s.key, s.color])).toEqual([
      ["g1", "var(--chart-0)"],
      ["g2", "var(--chart-1)"],
    ]);
    expect(rows).toHaveLength(12);
    expect(rows[1]).toMatchObject({
      month: 2,
      label: "Feb",
      g1: 450,
      g2: 200,
      total: 650,
      priorYearTotal: 420,
    });
    expect(rows[5]).toMatchObject({
      g1: 0,
      g2: 0,
      total: 0,
      priorYearTotal: 0,
    });
  });
});

describe("buildGroupRows", () => {
  it("builds month rows with deltas, categories, and links", () => {
    const rows = buildGroupRows(data, "month", ctx);
    expect(rows.map((r) => r.name)).toEqual(["Food & Dining", "Travel"]);
    const food = rows[0];
    expect(food).toMatchObject({
      amount: 450,
      share: 450 / 650,
      transactionCount: 9,
      delta: { pct: 12.5, isNew: false, label: "vs 3-mo avg" },
    });
    expect(food?.categories.map((c) => [c.name, c.amount])).toEqual([
      ["Dining Out", 300],
      ["Groceries", 150],
    ]);
    expect(food?.link.categoryNames).toEqual(["Dining Out", "Groceries"]);
    expect(food?.trend.map((p) => p.amount).slice(0, 3)).toEqual([400, 450, 0]);
    expect(food?.priorTrend?.[0]?.amount).toBe(380);
  });

  it("compares year to date against the prior year", () => {
    const rows = buildGroupRows(data, "ytd", ctx);
    const food = rows.find((r) => r.key === "g1");
    expect(food?.amount).toBe(850);
    expect(food?.delta).toEqual({
      pct: ((850 - 800) / 800) * 100,
      isNew: false,
      label: "vs 2025",
    });
    expect(rows.find((r) => r.key === "g2")?.delta?.isNew).toBe(true);
  });
});

describe("detectCreep", () => {
  const points = (amounts: number[]) =>
    amounts.map((amount, i) => ({ month: i + 1, amount }));

  it("flags three rising months", () => {
    expect(detectCreep(points([100, 110, 125, 140]), 4)).toEqual({
      direction: "up",
      months: 3,
    });
  });

  it("ignores short or flat runs and months after the selection", () => {
    expect(detectCreep(points([100, 102, 104, 106]), 4)).toBeNull();
    expect(detectCreep(points([100, 110, 125, 140]), 3)).toBeNull();
  });
});

describe("buildNotable", () => {
  it("lists the biggest swings and new categories with links", () => {
    const items = buildNotable(data, ctx);
    expect(items.map((i) => [i.kind, i.text])).toEqual([
      ["up", "Dining Out up 20% vs its 3-month average"],
      ["down", "Flights down 33% vs its 3-month average"],
      ["new", "Groceries is new this month"],
    ]);
    expect(items[0]?.link.categoryNames).toEqual(["Dining Out"]);
  });

  it("is empty without comparisons", () => {
    expect(buildNotable({ ...data, category_comparisons: [] }, ctx)).toEqual(
      [],
    );
  });
});
