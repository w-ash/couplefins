import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { renderWithProviders, screen, waitFor } from "@/test/test-utils";
import { SettingsPage } from "./SettingsPage";

const persons = [
  { id: "p1", name: "Alice", adjustment_account: "Alice Adj" },
  { id: "p2", name: "Bob", adjustment_account: "" },
];

const server = setupServer(
  http.get("/api/v1/category-groups", () => HttpResponse.json([])),
  http.get("/api/v1/category-mappings/unmapped", () => HttpResponse.json([])),
  http.get("/api/v1/persons/", () => HttpResponse.json(persons)),
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

  it("renders the people section with adjustment account settings", async () => {
    renderWithProviders(<SettingsPage />);
    expect(screen.getByRole("heading", { name: "People" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Alice")).toBeInTheDocument();
      expect(screen.getByText("Bob")).toBeInTheDocument();
    });
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
