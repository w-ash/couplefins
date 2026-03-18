import { fireEvent } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { useIdentityStore } from "@/lib/identity";
import { server } from "@/test/server";
import { renderWithProviders, screen, waitFor } from "../test/test-utils";
import { UploadPage } from "./UploadPage";

const persons = [
  { id: "p1", name: "Alice", adjustment_account: "adj-1" },
  { id: "p2", name: "Bob", adjustment_account: "adj-2" },
];

const previewResponseAllNew = {
  new_transactions: [
    {
      date: "2026-01-15",
      merchant: "Trader Joe's",
      category: "Groceries",
      amount: -50.0,
      is_shared: true,
      payer_percentage: 50,
    },
    {
      date: "2026-01-16",
      merchant: "Netflix",
      category: "Streaming",
      amount: -15.99,
      is_shared: false,
      payer_percentage: null,
    },
  ],
  unchanged_count: 0,
  changed_transactions: [],
  unmapped_categories: [],
};

const previewResponseNothingNew = {
  new_transactions: [],
  unchanged_count: 3,
  changed_transactions: [],
  unmapped_categories: [],
};

const previewResponseWithChanges = {
  new_transactions: [],
  unchanged_count: 1,
  changed_transactions: [
    {
      existing_id: "tx-123",
      incoming: {
        date: "2026-01-15",
        merchant: "Updated Store",
        category: "Groceries",
        amount: -50.0,
        is_shared: true,
        payer_percentage: 50,
      },
      existing: {
        date: "2026-01-15",
        merchant: "Old Store",
        category: "Groceries",
        amount: -50.0,
        is_shared: true,
        payer_percentage: 50,
      },
      diffs: [
        {
          field_name: "merchant",
          old_value: "Old Store",
          new_value: "Updated Store",
        },
      ],
    },
  ],
  unmapped_categories: [],
};

function setFileAndSubmit() {
  const fileInput = document.querySelector(
    'input[type="file"]',
  ) as HTMLInputElement;
  const file = new File(["Date,Merchant\n2026-01-15,Test"], "test.csv", {
    type: "text/csv",
  });
  fireEvent.change(fileInput, { target: { files: [file] } });
  const form = fileInput.closest("form") as HTMLFormElement;
  fireEvent.submit(form);
}

describe("UploadPage", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: "p1" });
    server.use(
      http.get("/api/v1/persons/", () => HttpResponse.json(persons)),
      http.get("/api/v1/uploads/history", () =>
        HttpResponse.json({ entries: [] }),
      ),
    );
  });

  it("renders the upload form without month/year", () => {
    renderWithProviders(<UploadPage />);
    expect(screen.getByText("Upload Transactions")).toBeInTheDocument();
    expect(screen.getByText("Who are you?")).toBeInTheDocument();
    expect(screen.queryByLabelText("Month")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Year")).not.toBeInTheDocument();
    expect(
      screen.getByText("Drop your CSV here, or click to browse"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Preview CSV" }),
    ).toBeInTheDocument();
  });

  it("disables preview button when no person selected", () => {
    useIdentityStore.setState({ currentPersonId: null });
    renderWithProviders(<UploadPage />);
    const button = screen.getByRole("button", { name: "Preview CSV" });
    expect(button).toBeDisabled();
  });

  it("shows new transactions preview with confirm button", async () => {
    server.use(
      http.post("/api/v1/uploads/preview", () =>
        HttpResponse.json(previewResponseAllNew),
      ),
    );

    renderWithProviders(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByText("Who are you?")).toBeInTheDocument();
    });

    setFileAndSubmit();

    await waitFor(() => {
      expect(screen.getByText("2 new transactions")).toBeInTheDocument();
    });

    expect(
      screen.getByRole("button", { name: "Confirm Import" }),
    ).toBeInTheDocument();
  });

  it("shows nothing-to-import message when all unchanged", async () => {
    server.use(
      http.post("/api/v1/uploads/preview", () =>
        HttpResponse.json(previewResponseNothingNew),
      ),
    );

    renderWithProviders(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByText("Who are you?")).toBeInTheDocument();
    });

    setFileAndSubmit();

    await waitFor(() => {
      expect(
        screen.getByText(/All transactions already imported/),
      ).toBeInTheDocument();
    });

    expect(
      screen.queryByRole("button", { name: "Confirm Import" }),
    ).not.toBeInTheDocument();
  });

  it("shows review step with checkboxes when changes detected", async () => {
    server.use(
      http.post("/api/v1/uploads/preview", () =>
        HttpResponse.json(previewResponseWithChanges),
      ),
    );

    renderWithProviders(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByText("Who are you?")).toBeInTheDocument();
    });

    setFileAndSubmit();

    await waitFor(() => {
      expect(screen.getByText("Review Changes")).toBeInTheDocument();
    });

    expect(screen.getByText("Accept All")).toBeInTheDocument();
    expect(screen.getByText("Reject All")).toBeInTheDocument();
    // The changed field diff values should be shown
    expect(screen.getByText("Old Store")).toBeInTheDocument();
    // "Updated Store" appears in both the merchant label and the diff new value
    expect(screen.getAllByText("Updated Store")).toHaveLength(2);
    // Checkbox should be checked by default
    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).toBeChecked();
  });

  it("shows upload history entries", async () => {
    server.use(
      http.get("/api/v1/uploads/history", () =>
        HttpResponse.json({
          entries: [
            {
              upload_id: "u1",
              person_id: "p1",
              person_name: "Alice",
              filename: "march-2026.csv",
              uploaded_at: new Date().toISOString(),
              transaction_count: 47,
              shared_count: 23,
              date_range_start: "2026-03-01",
              date_range_end: "2026-03-31",
            },
          ],
        }),
      ),
    );

    renderWithProviders(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByText("Past Uploads")).toBeInTheDocument();
    });
    expect(screen.getByText("march-2026.csv")).toBeInTheDocument();
    expect(screen.getByText("47 transactions")).toBeInTheDocument();
    expect(screen.getByText("23 shared")).toBeInTheDocument();
  });

  it("shows empty state when no upload history", async () => {
    renderWithProviders(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByText("No uploads yet")).toBeInTheDocument();
    });
  });

  it("shows error with role=alert on preview failure", async () => {
    server.use(
      http.post("/api/v1/uploads/preview", () =>
        HttpResponse.json(
          { error: { message: "Invalid CSV format" } },
          { status: 400 },
        ),
      ),
    );

    renderWithProviders(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByText("Who are you?")).toBeInTheDocument();
    });

    setFileAndSubmit();

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toHaveTextContent("Invalid CSV format");
    });
  });
});
