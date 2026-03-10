import { describe, expect, it } from "vitest";
import { renderWithProviders, screen, userEvent } from "@/test/test-utils";
import { ThemeToggle } from "./ThemeToggle";

describe("ThemeToggle", () => {
  it("renders three theme radio inputs", () => {
    renderWithProviders(<ThemeToggle />);
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(3);
  });

  it("has a group with label", () => {
    renderWithProviders(<ThemeToggle />);
    expect(
      screen.getByRole("group", { name: "Color theme" }),
    ).toBeInTheDocument();
  });

  it("defaults to system as checked", () => {
    window.localStorage.removeItem("couplefins:theme");
    renderWithProviders(<ThemeToggle />);
    const radios = screen.getAllByRole("radio");
    const systemRadio = radios.find(
      (r) => (r as HTMLInputElement).value === "system",
    );
    expect(systemRadio).toBeChecked();
  });

  it("switches active state on click", async () => {
    window.localStorage.removeItem("couplefins:theme");
    renderWithProviders(<ThemeToggle />);
    const user = userEvent.setup();
    const radios = screen.getAllByRole("radio");
    const darkRadio = radios.find(
      (r) => (r as HTMLInputElement).value === "dark",
    ) as HTMLInputElement;

    await user.click(darkRadio);

    expect(darkRadio).toBeChecked();
  });
});
