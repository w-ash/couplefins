import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/server";
import { renderWithProviders, screen, waitFor } from "@/test/test-utils";
import { TransactionEditHistory } from "./TransactionEditHistory";

const personNames = new Map([
  ["p1", "Alice"],
  ["p2", "Bob"],
]);

function mockEditsEndpoint(body: object) {
  server.use(
    http.get("*/api/v1/transactions/:id/edits", () => HttpResponse.json(body)),
  );
}

describe("TransactionEditHistory", () => {
  it("renders import event when no edits exist", async () => {
    mockEditsEndpoint({
      import_event: {
        person_id: "p1",
        imported_at: "2026-03-15T10:00:00Z",
      },
      edits: [],
    });

    renderWithProviders(
      <TransactionEditHistory transactionId="tx1" personNames={personNames} />,
    );

    await waitFor(() => {
      expect(screen.getByText(/Imported by/)).toBeInTheDocument();
    });
    expect(screen.getByText("Alice")).toBeInTheDocument();
  });

  it("renders full timeline with edits and import event", async () => {
    mockEditsEndpoint({
      import_event: {
        person_id: "p1",
        imported_at: "2026-03-15T10:00:00Z",
      },
      edits: [
        {
          id: "e1",
          transaction_id: "tx1",
          field_name: "category",
          old_value: "Dining Out",
          new_value: "Fast Food",
          edited_at: "2026-03-16T12:00:00Z",
          edited_by_person_id: "p2",
        },
        {
          id: "e2",
          transaction_id: "tx1",
          field_name: "amount",
          old_value: "-50.00",
          new_value: "-80.00",
          edited_at: "2026-03-17T14:00:00Z",
          edited_by_person_id: "p1",
        },
      ],
    });

    renderWithProviders(
      <TransactionEditHistory transactionId="tx1" personNames={personNames} />,
    );

    await waitFor(() => {
      expect(screen.getByText(/Bob/)).toBeInTheDocument();
    });
    expect(screen.getAllByText(/Alice/)).toHaveLength(2); // edit + import
    expect(screen.getByText(/Imported by/)).toBeInTheDocument();

    const list = screen.getByRole("list", { name: "Edit history" });
    expect(list).toBeInTheDocument();
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
  });

  it("omits person name for historical edits", async () => {
    mockEditsEndpoint({
      import_event: {
        person_id: "p1",
        imported_at: "2026-03-15T10:00:00Z",
      },
      edits: [
        {
          id: "e1",
          transaction_id: "tx1",
          field_name: "category",
          old_value: "Dining Out",
          new_value: "Fast Food",
          edited_at: "2026-03-16T12:00:00Z",
          edited_by_person_id: null,
        },
      ],
    });

    renderWithProviders(
      <TransactionEditHistory transactionId="tx1" personNames={personNames} />,
    );

    await waitFor(() => {
      expect(screen.getByText(/Changed/)).toBeInTheDocument();
    });
    // The edit line should not contain a person name before "changed"
    const items = screen.getAllByRole("listitem");
    const editItem = items[0];
    expect(editItem.textContent).toContain("Changed Category");
    expect(editItem.textContent).not.toContain("Alice changed");
    expect(editItem.textContent).not.toContain("Bob changed");
  });

  it("gracefully handles null import event", async () => {
    mockEditsEndpoint({
      import_event: null,
      edits: [
        {
          id: "e1",
          transaction_id: "tx1",
          field_name: "category",
          old_value: "Dining Out",
          new_value: "Fast Food",
          edited_at: "2026-03-16T12:00:00Z",
          edited_by_person_id: "p1",
        },
      ],
    });

    renderWithProviders(
      <TransactionEditHistory transactionId="tx1" personNames={personNames} />,
    );

    await waitFor(() => {
      expect(screen.getByText(/Alice/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Imported by/)).not.toBeInTheDocument();
  });
});
