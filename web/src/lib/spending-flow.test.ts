import { describe, expect, it } from "vitest";
import {
  ALICE,
  BOB,
  cell,
  MONTH_FLOW,
  makeFlowContext,
} from "@/test/insights-fixtures";
import {
  assignGroupColors,
  buildCategorySlices,
  buildGroupSlices,
  buildMerchantSlices,
  buildSankeyData,
  foldSlices,
  sourceLabel,
  UNCATEGORIZED_COLOR,
} from "./spending-flow";

const ctx = makeFlowContext();

describe("assignGroupColors", () => {
  it("assigns stable colors in the given order and mutes uncategorized", () => {
    const colors = assignGroupColors(["g2", "g1", null, "g2"]);
    expect(colors.get("g2")).toBe("var(--chart-0)");
    expect(colors.get("g1")).toBe("var(--chart-1)");
    expect(colors.get("uncategorized")).toBe(UNCATEGORIZED_COLOR);
  });
});

describe("sourceLabel", () => {
  it("speaks in the viewer's words", () => {
    expect(sourceLabel("payer", BOB.id, ctx)).toBe("Bob paid");
    expect(sourceLabel("household_share", BOB.id, ctx)).toBe(
      "My share of household",
    );
    expect(sourceLabel("personal", ALICE.id, ctx)).toBe("My personal");
    expect(sourceLabel("spotted_for_me", BOB.id, ctx)).toBe("Bob paid for me");
  });
});

describe("buildSankeyData", () => {
  it("links sources to groups to categories with matching sums", () => {
    const { nodes, links, droppedRefundOnly } = buildSankeyData(
      MONTH_FLOW.cells,
      ctx,
    );
    const names = nodes.map((n) => n.name);
    expect(names).toEqual([
      "Alice paid",
      "Bob paid",
      "Food & Dining",
      "Dining Out",
      "Groceries",
      "Travel",
      "Flights",
    ]);
    const into = (name: string) =>
      links
        .filter((l) => nodes[l.target]?.name === name)
        .reduce((s, l) => s + l.value, 0);
    const outOf = (name: string) =>
      links
        .filter((l) => nodes[l.source]?.name === name)
        .reduce((s, l) => s + l.value, 0);
    expect(into("Food & Dining")).toBe(450);
    expect(outOf("Food & Dining")).toBe(450);
    expect(outOf("Alice paid")).toBe(550);
    expect(outOf("Bob paid")).toBe(100);
    expect(droppedRefundOnly).toBe(0);
  });

  it("deep-links each node to its own Transactions list", () => {
    const { nodes } = buildSankeyData(MONTH_FLOW.cells, ctx);
    const byName = new Map(nodes.map((n) => [n.name, n.link]));
    expect(byName.get("Bob paid")).toEqual({
      range: { year: 2026, month: 2 },
      scope: "household",
      payerId: BOB.id,
    });
    expect(byName.get("Food & Dining")?.categoryNames).toEqual([
      "Dining Out",
      "Groceries",
    ]);
    expect(byName.get("Flights")?.categoryNames).toEqual(["Flights"]);
  });

  it("colors sources by person and categories by their group", () => {
    const { nodes } = buildSankeyData(MONTH_FLOW.cells, ctx);
    const color = (name: string) => nodes.find((n) => n.name === name)?.color;
    expect(color("Alice paid")).toBe("var(--person-0)");
    expect(color("Bob paid")).toBe("var(--person-1)");
    expect(color("Dining Out")).toBe("var(--chart-0)");
    expect(color("Flights")).toBe("var(--chart-1)");
  });

  it("folds the long tail of a group into Everything else", () => {
    const cells = [
      cell({ category: "A", amount: 500 }),
      cell({ category: "B", amount: 400 }),
      cell({ category: "C", amount: 300 }),
      cell({ category: "D", amount: 200 }),
      cell({ category: "E", amount: 5 }),
      cell({ category: "F", amount: 4 }),
      cell({ category: "G", amount: 3 }),
    ];
    const { nodes } = buildSankeyData(cells, ctx);
    const other = nodes.find((n) => n.kind === "other");
    expect(other?.name).toBe("Everything else (3)");
    expect(other?.amount).toBe(12);
    expect(other?.members).toEqual(["E", "F", "G"]);
    expect(other?.link.categoryNames).toEqual(["E", "F", "G"]);
    expect(nodes.some((n) => n.name === "E")).toBe(false);
  });

  it("keeps a category past the cap when it is a large share", () => {
    const cells = [
      cell({ category: "A", amount: 100 }),
      cell({ category: "B", amount: 100 }),
      cell({ category: "C", amount: 100 }),
      cell({ category: "D", amount: 100 }),
      cell({ category: "E", amount: 90 }),
      cell({ category: "F", amount: 1 }),
      cell({ category: "G", amount: 1 }),
    ];
    const { nodes } = buildSankeyData(cells, ctx);
    expect(nodes.some((n) => n.name === "E")).toBe(true);
    expect(nodes.find((n) => n.kind === "other")?.members).toEqual(["F", "G"]);
  });

  it("does not fold a single leftover", () => {
    const cells = ["A", "B", "C", "D", "E"].map((category, i) =>
      cell({ category, amount: 100 - i * 20 }),
    );
    const { nodes } = buildSankeyData(cells, ctx);
    expect(nodes.some((n) => n.kind === "other")).toBe(false);
    expect(nodes.some((n) => n.name === "E")).toBe(true);
  });

  it("drops refund-heavy cells and reports the count", () => {
    const cells = [
      cell({ amount: 100 }),
      cell({ category: "Refunds", amount: -20 }),
    ];
    const { nodes, droppedRefundOnly } = buildSankeyData(cells, ctx);
    expect(droppedRefundOnly).toBe(1);
    expect(nodes.some((n) => n.name === "Refunds")).toBe(false);
  });

  it("names the personal sources for My Spending", () => {
    const personal = makeFlowContext({ scope: "personal" });
    const cells = [
      cell({
        source_kind: "household_share",
        source_person_id: BOB.id,
        amount: 50,
      }),
      // My share of a household row I paid myself: the same source node.
      cell({
        source_kind: "household_share",
        source_person_id: ALICE.id,
        amount: 20,
      }),
      cell({
        source_kind: "personal",
        source_person_id: ALICE.id,
        amount: 40,
        category: "Groceries",
      }),
      cell({
        source_kind: "spotted_for_me",
        source_person_id: BOB.id,
        amount: 30,
        category: "Flights",
        group_id: "g2",
        group_name: "Travel",
      }),
    ];
    const { nodes } = buildSankeyData(cells, personal);
    const sources = nodes.filter((n) => n.kind === "source");
    expect(sources.map((n) => [n.name, n.color, n.amount])).toEqual([
      ["My share of household", "var(--household)", 70],
      ["My personal", "var(--person-0)", 40],
      ["Bob paid for me", "var(--person-1)", 30],
    ]);
    expect(sources[1]?.link).toEqual({
      range: { year: 2026, month: 2 },
      scope: "personal",
      payerId: ALICE.id,
    });
  });
});

describe("slices", () => {
  it("builds group slices with shares and category lists", () => {
    const slices = buildGroupSlices(MONTH_FLOW.cells, ctx);
    expect(slices.map((s) => [s.name, s.amount, s.share])).toEqual([
      ["Food & Dining", 450, 450 / 650],
      ["Travel", 200, 200 / 650],
    ]);
    expect(slices[0]?.link.categoryNames).toEqual(["Dining Out", "Groceries"]);
  });

  it("drills a group into its categories", () => {
    const slices = buildCategorySlices(MONTH_FLOW.cells, ctx, "g1");
    expect(slices.map((s) => [s.name, s.amount])).toEqual([
      ["Dining Out", 300],
      ["Groceries", 150],
    ]);
    expect(slices[0]?.share).toBeCloseTo(300 / 450);
  });

  it("links merchant slices with a search query", () => {
    const [airline] = buildMerchantSlices(MONTH_FLOW.top_merchants, ctx);
    expect(airline?.link).toEqual({
      range: { year: 2026, month: 2 },
      scope: "household",
      query: "Airline",
    });
    expect(airline?.color).toBe("var(--chart-1)");
  });

  it("folds slices beyond the cap into Everything else", () => {
    const cells = Array.from({ length: 12 }, (_, i) =>
      cell({ category: `C${i}`, amount: 120 - i * 10 }),
    );
    const slices = foldSlices(buildCategorySlices(cells, ctx), ctx, 8);
    expect(slices).toHaveLength(9);
    const other = slices[8];
    expect(other?.name).toBe("Everything else (4)");
    expect(other?.members).toEqual(["C8", "C9", "C10", "C11"]);
    expect(other?.link.categoryNames).toEqual(["C8", "C9", "C10", "C11"]);
    expect(slices.reduce((s, x) => s + x.share, 0)).toBeCloseTo(1);
  });

  it("leaves nine slices alone rather than folding one", () => {
    const cells = Array.from({ length: 9 }, (_, i) =>
      cell({ category: `C${i}`, amount: 100 - i }),
    );
    expect(foldSlices(buildCategorySlices(cells, ctx), ctx, 8)).toHaveLength(9);
  });
});

describe("buildSankeyData global cap", () => {
  it("trims the smallest survivors so the right column stays readable", () => {
    const cells = Array.from({ length: 12 }, (_, g) =>
      ["A", "B", "C"].map((suffix, i) =>
        cell({
          group_id: `g${g}`,
          group_name: `Group ${g}`,
          category: `G${g}-${suffix}`,
          amount: 300 - g * 10 - i,
        }),
      ),
    ).flat();
    const { nodes } = buildSankeyData(cells, ctx);
    const categories = nodes.filter((n) => n.kind === "category");
    const others = nodes.filter((n) => n.kind === "other");
    expect(categories).toHaveLength(14);
    expect(others.length).toBeGreaterThan(0);
    // Every folded node still links to its exact categories.
    for (const other of others)
      expect(other.link.categoryNames).toEqual(other.members);
  });
});
