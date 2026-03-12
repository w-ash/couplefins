import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import type { Person } from "@/types/person";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "../test/test-utils";
import { AdjustmentExportSection } from "./AdjustmentExportSection";

const persons: Person[] = [
  { id: "p1", name: "Alice", adjustment_account: "Alice Adjustments" },
  { id: "p2", name: "Bob", adjustment_account: "" },
];

const previewResponse = {
  adjustments: [
    {
      dedup_id: "abc123def456",
      date: "2026-01-15",
      merchant: "Restaurant",
      category: "Dining Out",
      amount: 50.0,
    },
    {
      dedup_id: "fed654cba321",
      date: "2026-01-20",
      merchant: "Grocery Store",
      category: "Groceries",
      amount: -30.0,
    },
  ],
  person_name: "Alice",
  adjustment_count: 2,
};

const server = setupServer(
  http.get("/api/v1/persons/:personId/adjustments/:year/:month", () =>
    HttpResponse.json(previewResponse),
  ),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderSection(overrides?: { persons?: Person[] }) {
  return renderWithProviders(
    <AdjustmentExportSection
      persons={overrides?.persons ?? persons}
      year={2026}
      month={1}
    />,
  );
}

describe("AdjustmentExportSection", () => {
  it("renders export buttons for both persons", () => {
    renderSection();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("disables download when adjustment_account is empty", () => {
    renderSection();
    const buttons = screen.getAllByRole("button", {
      name: /Download Adjustments/,
    });
    // Alice has account → enabled, Bob doesn't → disabled
    expect(buttons[0]).not.toBeDisabled();
    expect(buttons[1]).toBeDisabled();
  });

  it("shows inline explanation when account not set", () => {
    renderSection();
    expect(
      screen.getByText(/Set adjustment account in Settings/),
    ).toBeInTheDocument();
  });

  it("expands preview on click and shows adjustment rows", async () => {
    const user = userEvent.setup();
    renderSection();

    const previewButtons = screen.getAllByRole("button", { name: /Preview/ });
    await user.click(previewButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("Restaurant")).toBeInTheDocument();
      expect(screen.getByText("Grocery Store")).toBeInTheDocument();
    });
  });

  it("shows empty preview message when no adjustments", async () => {
    server.use(
      http.get("/api/v1/persons/:personId/adjustments/:year/:month", () =>
        HttpResponse.json({
          adjustments: [],
          person_name: "Alice",
          adjustment_count: 0,
        }),
      ),
    );

    const user = userEvent.setup();
    renderSection();

    const previewButtons = screen.getAllByRole("button", { name: /Preview/ });
    await user.click(previewButtons[0]);

    await waitFor(() => {
      expect(
        screen.getByText("No adjustments for this month."),
      ).toBeInTheDocument();
    });
  });

  it("disables preview button when account not set", () => {
    renderSection();
    const previewButtons = screen.getAllByRole("button", { name: /Preview/ });
    // Bob's preview button should be disabled
    expect(previewButtons[1]).toBeDisabled();
  });
});
