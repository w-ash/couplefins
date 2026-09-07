import { within } from "@testing-library/react";
import { useSearchParams } from "react-router";
import { describe, expect, it } from "vitest";
import { renderWithProviders, screen, userEvent } from "../test/test-utils";
import { MonthPicker } from "./MonthPicker";

function UrlProbe() {
  const [params] = useSearchParams();
  return <span data-testid="url">{params.toString()}</span>;
}

describe("MonthPicker", () => {
  it("labels the trigger with the month it was given", () => {
    renderWithProviders(<MonthPicker value={{ year: 2025, month: 3 }} />, {
      routerProps: { initialEntries: ["/?month=9&year=2020"] },
    });
    expect(
      screen.getByRole("button", { name: "Select month" }),
    ).toHaveTextContent("March 2025");
  });

  it("opens popover on click and shows month grid", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MonthPicker value={{ year: 2026, month: 6 }} />, {
      routerProps: { initialEntries: ["/?month=6&year=2026"] },
    });

    await user.click(screen.getByRole("button", { name: "Select month" }));
    const dialog = screen.getByRole("dialog", { name: "Choose month" });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText("Jan")).toBeInTheDocument();
    expect(within(dialog).getByText("Dec")).toBeInTheDocument();
    expect(within(dialog).getByText("2026")).toBeInTheDocument();
  });

  it("navigates years with chevron buttons", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MonthPicker value={{ year: 2026, month: 1 }} />, {
      routerProps: { initialEntries: ["/?month=1&year=2026"] },
    });

    await user.click(screen.getByRole("button", { name: "Select month" }));
    const dialog = screen.getByRole("dialog", { name: "Choose month" });
    expect(dialog).toBeInTheDocument();

    const prevBtn = within(dialog).getByRole("button", {
      name: "Previous year",
    });
    const nextBtn = within(dialog).getByRole("button", { name: "Next year" });

    await user.click(prevBtn);
    expect(within(dialog).getByText("2025")).toBeInTheDocument();

    await user.click(nextBtn);
    expect(within(dialog).getByText("2026")).toBeInTheDocument();
  });

  it("sits inert while the month is unresolved", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MonthPicker value={null} />);

    const trigger = screen.getByRole("button", { name: "Select month" });
    expect(trigger).toBeDisabled();

    await user.click(trigger);
    expect(
      screen.queryByRole("dialog", { name: "Choose month" }),
    ).not.toBeInTheDocument();
  });

  it("still writes the URL when controlled", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <MonthPicker value={{ year: 2026, month: 6 }} />
        <UrlProbe />
      </>,
    );

    await user.click(screen.getByRole("button", { name: "Select month" }));
    const dialog = screen.getByRole("dialog", { name: "Choose month" });
    await user.click(within(dialog).getByText("Mar"));

    // Picking is what makes a resolved month explicit and shareable.
    expect(screen.getByTestId("url")).toHaveTextContent("year=2026&month=3");
  });

  it("closes popover after selecting a month", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MonthPicker value={{ year: 2026, month: 6 }} />, {
      routerProps: { initialEntries: ["/?month=6&year=2026"] },
    });

    await user.click(screen.getByRole("button", { name: "Select month" }));
    const dialog = screen.getByRole("dialog", { name: "Choose month" });
    await user.click(within(dialog).getByText("Mar"));

    expect(
      screen.queryByRole("dialog", { name: "Choose month" }),
    ).not.toBeInTheDocument();
    // The label follows the value the page hands back, not the pick itself.
    expect(
      screen.getByRole("button", { name: "Select month" }),
    ).toHaveTextContent("June 2026");
  });
});
