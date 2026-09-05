import { HttpResponse, http } from "msw";
import { act } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/test/server";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/test/test-utils";
import { CategoryMappingEditor } from "./CategoryMappingEditor";

const groups = [
  {
    id: "g1",
    name: "Food & Dining",
    icon: "utensils-crossed",
    kind: "expense",
    categories: [
      { name: "Groceries", include_personal: false },
      { name: "Dining Out", include_personal: false },
    ],
  },
  {
    id: "g2",
    name: "Home Expenses",
    icon: "home",
    kind: "expense",
    categories: [{ name: "Rent", include_personal: false }],
  },
  {
    id: "g3",
    name: "Empty Group",
    icon: null,
    kind: "expense",
    categories: [],
  },
  {
    id: "g4",
    name: "Money Movement",
    icon: "arrow-left-right",
    kind: "transfer",
    categories: [
      { name: "Credit Card Payment", include_personal: false },
      { name: "Balance Adjustment", include_personal: false },
      { name: "Wire", include_personal: false },
    ],
  },
];

/** Click a group's header to expand it, then click a button in its action bar. */
async function expandAndClickAction(groupName: string, actionName: string) {
  await userEvent.click(screen.getByText(groupName));
  // Action bars are in the DOM for all groups (CSS-hidden when collapsed).
  // After expanding, click the first visible one matching the action name.
  const buttons = screen.getAllByText(actionName);
  // Find the button that's inside a visible (expanded) area
  const visibleButton = buttons.find((btn) => {
    const overflowParent = btn.closest(".overflow-hidden");
    if (!overflowParent) return true;
    const gridParent = overflowParent.parentElement;
    return gridParent?.style.gridTemplateRows === "1fr";
  });
  if (!visibleButton)
    throw new Error(`No visible "${actionName}" button found`);
  await userEvent.click(visibleButton);
}

describe("CategoryMappingEditor", () => {
  beforeEach(() => {
    server.use(
      http.get("/api/v1/category-groups", () => HttpResponse.json(groups)),
      http.get("/api/v1/category-mappings/unmapped", () =>
        HttpResponse.json([]),
      ),
      http.get("/api/v1/budgets", () => HttpResponse.json([])),
    );
  });

  it("renders group cards after loading", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });
    expect(screen.getByText("Home Expenses")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    renderWithProviders(<CategoryMappingEditor />);
    expect(screen.getByText("Loading categories...")).toBeInTheDocument();
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
    const comboboxes = screen.getAllByRole("combobox");
    expect(comboboxes.length).toBeGreaterThanOrEqual(2);
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
    expect(
      screen.getByRole("button", { name: "Try Again" }),
    ).toBeInTheDocument();
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

  it("shows categories when expanded", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText("Food & Dining"));

    await waitFor(() => {
      expect(screen.getByText("Groceries")).toBeInTheDocument();
    });
    expect(screen.getByText("Dining Out")).toBeInTheDocument();
  });

  it("shows action bar buttons in DOM for all groups", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });

    // All groups have action bar buttons in the DOM (CSS-hidden when collapsed)
    expect(screen.getAllByText("Change Icon")).toHaveLength(4);
    expect(screen.getAllByText("Rename")).toHaveLength(4);
    expect(screen.getAllByText("Delete Group")).toHaveLength(4);
  });

  it("shows rename input when Rename is clicked", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });

    await expandAndClickAction("Food & Dining", "Rename");

    await waitFor(() => {
      expect(screen.getByLabelText("Group name")).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Group name")).toHaveValue("Food & Dining");
    // Action bar switches to Save/Cancel (visible in the expanded group's action bar)
    expect(screen.getByText("Save")).toBeInTheDocument();
    // "Cancel" also exists in dialog buttons, so verify at least one exists
    expect(screen.getAllByText("Cancel").length).toBeGreaterThanOrEqual(1);
  });

  it("shows delete dialog with combobox for group with categories", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });

    await expandAndClickAction("Food & Dining", "Delete Group");

    const dialog = await screen.findByRole("dialog");
    const dialogContent = within(dialog);
    expect(
      dialogContent.getByText("2 categories will need a new home."),
    ).toBeInTheDocument();
    expect(dialogContent.getByText("Move to")).toBeInTheDocument();
    expect(
      dialogContent.getByRole("button", { name: "Move & Remove" }),
    ).toBeDisabled();
    expect(
      dialogContent.getByRole("button", { name: "Cancel" }),
    ).toBeInTheDocument();
  });

  it("shows simple delete dialog for empty group", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Empty Group")).toBeInTheDocument();
    });

    await expandAndClickAction("Empty Group", "Delete Group");

    const dialog = await screen.findByRole("dialog");
    const dialogContent = within(dialog);
    expect(dialogContent.getByText("This group is empty.")).toBeInTheDocument();
    expect(
      dialogContent.getByRole("button", { name: "Remove Group" }),
    ).not.toBeDisabled();
  });

  it("dialog has aria-modal when open", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });

    await expandAndClickAction("Food & Dining", "Delete Group");

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    });
  });

  it("closes dialog on Escape via close event", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });

    await expandAndClickAction("Food & Dining", "Delete Group");

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();

    act(() => {
      (dialog as HTMLDialogElement).close();
    });

    await waitFor(() => {
      expect(dialog).not.toHaveAttribute("open");
    });
  });

  it("shows budget info in delete dialog when budgets exist", async () => {
    server.use(
      http.get("/api/v1/budgets", () =>
        HttpResponse.json([
          {
            id: "b1",
            group_id: "g1",
            monthly_amount: 500,
            year: 2026,
            month: 1,
          },
        ]),
      ),
    );

    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });

    await expandAndClickAction("Food & Dining", "Delete Group");

    const dialog = await screen.findByRole("dialog");
    const dialogContent = within(dialog);

    await waitFor(() => {
      expect(
        dialogContent.getByText(/budget will also be removed/),
      ).toBeInTheDocument();
    });
  });

  it("marks a transfer group with a pill and caption", async () => {
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Money Movement")).toBeInTheDocument();
    });

    // Collapsed pill is visible; the caption lives in the expanded panel.
    expect(
      screen.getByTitle(/Transfer — money movement, not spending/),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Excluded from spending, budgets, and settlement"),
    ).toBeInTheDocument();
  });

  it("changing the kind PUTs name, icon, and kind together", async () => {
    let body: unknown = null;
    server.use(
      http.put("/api/v1/category-groups/g1", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...groups[0], kind: "transfer" });
      }),
    );
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Food & Dining")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByText("Food & Dining"));

    // Each card has its own Spending/Transfer control; the first belongs to g1.
    const transferRadios = screen.getAllByRole("radio", { name: "Transfer" });
    await userEvent.click(transferRadios[0]);

    await waitFor(() => {
      expect(body).toEqual({
        name: "Food & Dining",
        icon: "utensils-crossed",
        kind: "transfer",
      });
    });
  });

  it("rename keeps the group's kind", async () => {
    let body: unknown = null;
    server.use(
      http.put("/api/v1/category-groups/g4", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...groups[3], name: "Transfers" });
      }),
    );
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByText("Money Movement")).toBeInTheDocument();
    });
    await expandAndClickAction("Money Movement", "Rename");
    const input = screen.getByLabelText("Group name");
    await userEvent.clear(input);
    await userEvent.type(input, "Transfers{Enter}");

    await waitFor(() => {
      expect(body).toEqual({
        name: "Transfers",
        icon: "arrow-left-right",
        kind: "transfer",
      });
    });
  });

  it("add group form sends the chosen kind", async () => {
    let body: unknown = null;
    server.use(
      http.post("/api/v1/category-groups", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          {
            id: "g9",
            name: "Card Payments",
            icon: null,
            kind: "transfer",
            categories: [],
          },
          { status: 201 },
        );
      }),
    );
    renderWithProviders(<CategoryMappingEditor />);

    await waitFor(() => {
      expect(screen.getByLabelText("New group name")).toBeInTheDocument();
    });
    await userEvent.type(
      screen.getByLabelText("New group name"),
      "Card Payments",
    );
    // The add form's control is the last Spending/Transfer control on the page.
    const transferRadios = screen.getAllByRole("radio", { name: "Transfer" });
    await userEvent.click(transferRadios[transferRadios.length - 1]);
    await userEvent.click(screen.getByRole("button", { name: "Add Group" }));

    await waitFor(() => {
      expect(body).toEqual({ name: "Card Payments", kind: "transfer" });
    });
  });
});
