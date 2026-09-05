import { describe, expect, it, vi } from "vitest";
import {
  buildCategorySlices,
  buildGroupSlices,
  foldSlices,
} from "@/lib/spending-flow";
import { cell, MONTH_FLOW, makeFlowContext } from "@/test/insights-fixtures";
import { renderWithProviders, screen, userEvent } from "@/test/test-utils";
import { SpendingLegendTable } from "./SpendingLegendTable";

const ctx = makeFlowContext();

describe("SpendingLegendTable", () => {
  it("renders rows with amounts, shares, and links", () => {
    renderWithProviders(
      <SpendingLegendTable slices={buildGroupSlices(MONTH_FLOW.cells, ctx)} />,
    );
    expect(screen.getByRole("link", { name: /Travel/ })).toHaveAttribute(
      "href",
      "/transactions?year=2026&month=2&scope=household&cat=Flights",
    );
    expect(screen.getByText("$200.00")).toBeInTheDocument();
    expect(screen.getByText("31%")).toBeInTheDocument();
  });

  it("drills a row when allowed and shows the breadcrumb", async () => {
    const onDrill = vi.fn();
    const onBack = vi.fn();
    renderWithProviders(
      <SpendingLegendTable
        slices={buildGroupSlices(MONTH_FLOW.cells, ctx)}
        canDrill={() => true}
        onDrill={onDrill}
        breadcrumb={{ label: "Food & Dining", onBack }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Travel/ }));
    expect(onDrill).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Travel" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "All groups" }));
    expect(onBack).toHaveBeenCalled();
  });

  it("expands Everything else to show its members and a link", async () => {
    const cells = Array.from({ length: 11 }, (_, i) =>
      cell({ category: `Cat ${i}`, amount: 100 - i }),
    );
    const slices = foldSlices(buildCategorySlices(cells, ctx), ctx, 8);
    renderWithProviders(<SpendingLegendTable slices={slices} />);
    const toggle = screen.getByRole("button", {
      name: /Everything else \(3\)/,
    });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(toggle);
    expect(screen.getByText(/Cat 8, Cat 9, Cat 10/)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "View transactions" }),
    ).toHaveAttribute(
      "href",
      "/transactions?year=2026&month=2&scope=household&cat=Cat+8&cat=Cat+9&cat=Cat+10",
    );
  });
});
