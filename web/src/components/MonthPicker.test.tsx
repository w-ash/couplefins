import { describe, expect, it } from "vitest";
import { renderWithProviders, screen, userEvent } from "../test/test-utils";
import { MonthPicker } from "./MonthPicker";

describe("MonthPicker", () => {
  it("renders button with current month label", () => {
    renderWithProviders(<MonthPicker />);
    const now = new Date();
    const monthName = now.toLocaleString("en-US", { month: "long" });
    expect(
      screen.getByRole("button", { name: "Select month" }),
    ).toHaveTextContent(`${monthName} ${now.getFullYear()}`);
  });

  it("reads month/year from URL search params", () => {
    renderWithProviders(<MonthPicker />, {
      routerProps: { initialEntries: ["/?month=3&year=2025"] },
    });
    expect(
      screen.getByRole("button", { name: "Select month" }),
    ).toHaveTextContent("March 2025");
  });

  it("opens popover on click and shows month grid", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MonthPicker />, {
      routerProps: { initialEntries: ["/?month=6&year=2026"] },
    });

    await user.click(screen.getByRole("button", { name: "Select month" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Jan")).toBeInTheDocument();
    expect(screen.getByText("Dec")).toBeInTheDocument();
    expect(screen.getByText("2026")).toBeInTheDocument();
  });

  it("navigates years with chevron buttons", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MonthPicker />, {
      routerProps: { initialEntries: ["/?month=1&year=2026"] },
    });

    await user.click(screen.getByRole("button", { name: "Select month" }));
    expect(screen.getByText("2026")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Previous year" }));
    expect(screen.getByText("2025")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next year" }));
    expect(screen.getByText("2026")).toBeInTheDocument();
  });

  it("closes popover after selecting a month", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MonthPicker />, {
      routerProps: { initialEntries: ["/?month=6&year=2026"] },
    });

    await user.click(screen.getByRole("button", { name: "Select month" }));
    await user.click(screen.getByText("Mar"));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Select month" }),
    ).toHaveTextContent("March 2026");
  });
});
