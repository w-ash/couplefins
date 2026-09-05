import { describe, expect, it } from "vitest";
import { buildGroupRows } from "@/lib/insights-data";
import { makeFlowContext, makeSpendingTrends } from "@/test/insights-fixtures";
import { renderWithProviders, screen, userEvent } from "@/test/test-utils";
import { GroupBreakdownTable } from "./GroupBreakdownTable";

const data = makeSpendingTrends();

describe("GroupBreakdownTable", () => {
  it("shows a row per group with amount, share, change, and a link", () => {
    const rows = buildGroupRows(data, "month", makeFlowContext());
    renderWithProviders(
      <GroupBreakdownTable rows={rows} iconMap={new Map()} selectedMonth={2} />,
    );
    expect(screen.getByText("$450.00")).toBeInTheDocument();
    expect(screen.getByText("69%")).toBeInTheDocument();
    expect(screen.getByText("+13%")).toBeInTheDocument();
    expect(screen.getByText("-33%")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "View Travel transactions" }),
    ).toHaveAttribute(
      "href",
      "/transactions?year=2026&month=2&scope=household&cat=Flights",
    );
  });

  it("expands to categories that link with the personal scope and a YTD range", async () => {
    const rows = buildGroupRows(
      data,
      "ytd",
      makeFlowContext({
        scope: "personal",
        range: { startDate: "2026-01-01", endDate: "2026-02-28" },
      }),
    );
    renderWithProviders(
      <GroupBreakdownTable rows={rows} iconMap={new Map()} selectedMonth={2} />,
    );
    const toggle = screen.getByRole("button", { name: /Food & Dining/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(toggle);
    expect(screen.getByRole("link", { name: /Dining Out/ })).toHaveAttribute(
      "href",
      "/transactions?startDate=2026-01-01&endDate=2026-02-28&scope=personal&cat=Dining+Out",
    );
    expect(screen.getByText("New")).toBeInTheDocument();
  });
});
