import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { act } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/test/test-utils";
import { CategoryMappingEditor } from "./CategoryMappingEditor";

const groups = [
  { id: "g1", name: "Food & Dining", categories: ["Groceries", "Dining Out"] },
  { id: "g2", name: "Home Expenses", categories: ["Rent"] },
];

const server = setupServer(
  http.get("/api/v1/category-groups", () => HttpResponse.json(groups)),
  http.get("/api/v1/category-mappings/unmapped", () => HttpResponse.json([])),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("CategoryMappingEditor", () => {
  it("renders group cards after loading", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });
    expect(screen.getByText("Home Expenses")).toBeInTheDocument();
    // Category counts shown
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("shows skeleton while loading", () => {
    renderWithProviders(<CategoryMappingEditor />);
    expect(
      screen.getByRole("status", { name: "Loading categories" }),
    ).toBeInTheDocument();
  });

  it("shows unmapped categories banner", async () => {
    server.use(
      http.get("/api/v1/category-mappings/unmapped", () =>
        HttpResponse.json(["Mystery", "Unknown"]),
      ),
    );

    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("2 unmapped categories")).toBeInTheDocument();
    });
    expect(screen.getByText("Mystery")).toBeInTheDocument();
    expect(screen.getByText("Unknown")).toBeInTheDocument();
    // Each unmapped category has a dropdown
    expect(
      screen.getByLabelText("Assign Mystery to group"),
    ).toBeInTheDocument();
  });

  it("shows empty state when no groups or unmapped", async () => {
    server.use(
      http.get("/api/v1/category-groups", () => HttpResponse.json([])),
    );

    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText(/No categories yet/)).toBeInTheDocument();
    });
    expect(screen.getByText("Upload a CSV")).toBeInTheDocument();
  });

  it("shows error state with retry", async () => {
    server.use(
      http.get("/api/v1/category-groups", () =>
        HttpResponse.json(null, { status: 500 }),
      ),
    );

    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to load categories."),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("shows delete confirmation dialog", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });

    const deleteBtn = screen.getByLabelText("Delete Food & Dining");
    await userEvent.click(deleteBtn);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(
      screen.getByText("2 categories will become unmapped."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Remove Group" }),
    ).toBeInTheDocument();
  });

  it("dialog has aria-modal when open", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByLabelText("Delete Food & Dining"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    });
  });

  it("closes dialog on Escape via close event", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByLabelText("Delete Food & Dining"));

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();

    // Simulate the browser's Escape behavior: calling .close() dispatches "close" event
    act(() => {
      (dialog as HTMLDialogElement).close();
    });

    await waitFor(() => {
      expect(dialog).not.toHaveAttribute("open");
    });
  });

  it("has add group form", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });

    expect(screen.getByLabelText("New group name")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add Group" }),
    ).toBeInTheDocument();
  });
});
