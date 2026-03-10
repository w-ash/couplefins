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
      screen.getByText(
        "Monarch categories map to budget groups like Food & Dining or Home Expenses. This will be configurable once budget tracking arrives.",
      ),
    ).toBeInTheDocument();
  });

  it("renders the people placeholder", () => {
    renderWithProviders(<SettingsPage />);
    expect(screen.getByRole("heading", { name: "People" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Both profiles were created during setup. Name editing and other profile options will appear here in a future update.",
      ),
    ).toBeInTheDocument();
  });

  it("has aria-labelledby on each section", () => {
    renderWithProviders(<SettingsPage />);
    const sections = screen.getAllByRole("region");
    expect(sections).toHaveLength(3);

    expect(sections[0]).toHaveAttribute(
      "aria-labelledby",
      "settings-appearance",
    );
    expect(sections[1]).toHaveAttribute(
      "aria-labelledby",
      "settings-category-mappings",
    );
    expect(sections[2]).toHaveAttribute("aria-labelledby", "settings-people");
  });
});
