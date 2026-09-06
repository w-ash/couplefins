import { describe, expect, it } from "vitest";
import { buildCategorySlices, foldSlices } from "@/lib/spending-flow";
import { cell, makeFlowContext } from "@/test/insights-fixtures";
import { renderWithProviders, screen } from "@/test/test-utils";
import { SpendingBars } from "./SpendingBars";

describe("SpendingBars", () => {
  it("scales every bar to the widest one, including Everything else", () => {
    const ctx = makeFlowContext();
    const cells = Array.from({ length: 12 }, (_, i) =>
      cell({ category: `C${i}`, amount: 100 }),
    );
    const slices = foldSlices(buildCategorySlices(cells, ctx), ctx, 8);
    renderWithProviders(<SpendingBars slices={slices} />);
    const other = screen.getByRole("link", { name: /Everything else \(4\)/ });
    const fill = other.querySelector("div > div") as HTMLElement;
    expect(fill.style.width).toBe("100%");
    const first = screen.getByRole("link", { name: /C0/ });
    expect((first.querySelector("div > div") as HTMLElement).style.width).toBe(
      "25%",
    );
  });
});
