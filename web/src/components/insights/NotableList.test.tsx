import { describe, expect, it } from "vitest";
import { buildNotable } from "@/lib/insights-data";
import { makeFlowContext, makeSpendingTrends } from "@/test/insights-fixtures";
import { renderWithProviders, screen } from "@/test/test-utils";
import { NotableList } from "./NotableList";

describe("NotableList", () => {
  it("renders each item as a link with its amount", () => {
    const items = buildNotable(makeSpendingTrends(), makeFlowContext());
    renderWithProviders(<NotableList items={items} />);
    expect(
      screen.getByRole("link", { name: /Flights down 33%/ }),
    ).toHaveAttribute(
      "href",
      "/transactions?year=2026&month=2&scope=household&cat=Flights",
    );
    expect(screen.getByText("$300.00")).toBeInTheDocument();
  });
});
