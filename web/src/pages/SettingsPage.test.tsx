import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/test/test-utils";
import { SettingsPage } from "./SettingsPage";

describe("SettingsPage", () => {
  it("renders the settings heading", () => {
    renderWithProviders(<SettingsPage />);
    expect(
      screen.getByRole("heading", { name: "Settings" }),
    ).toBeInTheDocument();
  });

  it("renders the appearance section with theme toggle", () => {
    renderWithProviders(<SettingsPage />);
    expect(
      screen.getByRole("heading", { name: "Appearance" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Theme")).toBeInTheDocument();
    // ThemeToggle renders Light/System/Dark radio buttons
    expect(screen.getByLabelText("Light")).toBeInTheDocument();
    expect(screen.getByLabelText("System")).toBeInTheDocument();
    expect(screen.getByLabelText("Dark")).toBeInTheDocument();
  });

  it("renders the category mappings placeholder", () => {
    renderWithProviders(<SettingsPage />);
    expect(
      screen.getByRole("heading", { name: "Category Mappings" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Category group management coming in a future update."),
    ).toBeInTheDocument();
  });

  it("renders the people placeholder", () => {
    renderWithProviders(<SettingsPage />);
    expect(screen.getByRole("heading", { name: "People" })).toBeInTheDocument();
    expect(
      screen.getByText("Person configuration coming in a future update."),
    ).toBeInTheDocument();
  });
});
