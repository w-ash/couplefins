import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { renderWithProviders, screen, waitFor } from "@/test/test-utils";
import { SettingsPage } from "./SettingsPage";

const server = setupServer(
  http.get("/api/v1/category-groups", () => HttpResponse.json([])),
  http.get("/api/v1/category-mappings/unmapped", () => HttpResponse.json([])),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

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
    expect(screen.getByLabelText("Light")).toBeInTheDocument();
    expect(screen.getByLabelText("System")).toBeInTheDocument();
    expect(screen.getByLabelText("Dark")).toBeInTheDocument();
  });

  it("renders the category groups section", () => {
    renderWithProviders(<SettingsPage />);
    expect(
      screen.getByRole("heading", { name: "Category Groups" }),
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

  it("shows empty state when no categories exist", async () => {
    renderWithProviders(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/No categories yet/)).toBeInTheDocument();
    });

    expect(screen.getByText("Upload a CSV")).toBeInTheDocument();
  });
});
