import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/test/server";
import { renderWithProviders, screen, waitFor } from "@/test/test-utils";
import { SettingsPage } from "./SettingsPage";

const persons = [
  {
    id: "p1",
    name: "Alice",
    adjustment_account: "Alice Adj",
    theme_preference: "system",
  },
  { id: "p2", name: "Bob", adjustment_account: "", theme_preference: "system" },
];

const healthResponse = {
  status: "ok",
  database_host: "localhost",
  database_mode: "Local PostgreSQL",
};

describe("SettingsPage", () => {
  beforeEach(() => {
    server.use(
      http.get("/api/v1/category-groups", () => HttpResponse.json([])),
      http.get("/api/v1/category-mappings/unmapped", () =>
        HttpResponse.json([]),
      ),
      http.get("/api/v1/persons/", () => HttpResponse.json(persons)),
      http.get("/api/v1/health", () => HttpResponse.json(healthResponse)),
      http.get("/api/v1/settings/settlement-merchants", () =>
        HttpResponse.json([]),
      ),
    );
  });
  it("renders the settings heading", () => {
    renderWithProviders(<SettingsPage />);
    expect(
      screen.getByRole("heading", { name: "Settings" }),
    ).toBeInTheDocument();
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

  it("has aria-labelledby on each section", async () => {
    renderWithProviders(<SettingsPage />);

    await waitFor(() => {
      const sections = screen.getAllByRole("region");
      expect(sections).toHaveLength(4);

      expect(sections[0]).toHaveAttribute(
        "aria-labelledby",
        "settings-category-mappings",
      );
      expect(sections[1]).toHaveAttribute("aria-labelledby", "settings-people");
      expect(sections[2]).toHaveAttribute(
        "aria-labelledby",
        "settings-settlement-merchants",
      );
      expect(sections[3]).toHaveAttribute("aria-labelledby", "settings-system");
    });
  });

  it("shows empty state when no categories exist", async () => {
    renderWithProviders(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/No categories yet/)).toBeInTheDocument();
    });

    expect(screen.getByText("Upload a CSV")).toBeInTheDocument();
  });

  it("shows database info in system section", async () => {
    renderWithProviders(<SettingsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "System" }),
      ).toBeInTheDocument();
      expect(screen.getByText("Local PostgreSQL")).toBeInTheDocument();
      expect(screen.getByText("localhost")).toBeInTheDocument();
    });
  });
});
