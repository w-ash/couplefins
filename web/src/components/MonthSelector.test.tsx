import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "../test/test-utils";
import { MonthSelector } from "./MonthSelector";

describe("MonthSelector", () => {
  it("renders month and year selects", () => {
    renderWithProviders(<MonthSelector />);
    expect(screen.getByLabelText("Month")).toBeInTheDocument();
    expect(screen.getByLabelText("Year")).toBeInTheDocument();
  });

  it("defaults to current month and year", () => {
    renderWithProviders(<MonthSelector />);
    const monthSelect = screen.getByLabelText("Month") as HTMLSelectElement;
    const yearSelect = screen.getByLabelText("Year") as HTMLSelectElement;
    const now = new Date();
    expect(monthSelect.value).toBe(String(now.getMonth() + 1));
    expect(yearSelect.value).toBe(String(now.getFullYear()));
  });

  it("reads month/year from URL search params", () => {
    renderWithProviders(<MonthSelector />, {
      routerProps: { initialEntries: ["/?month=3&year=2025"] },
    });
    const monthSelect = screen.getByLabelText("Month") as HTMLSelectElement;
    const yearSelect = screen.getByLabelText("Year") as HTMLSelectElement;
    expect(monthSelect.value).toBe("3");
    expect(yearSelect.value).toBe("2025");
  });
});
