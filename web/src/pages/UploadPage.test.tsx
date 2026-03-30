import { fireEvent } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { useIdentityStore } from "@/lib/identity";
import { server } from "@/test/server";
import { renderWithProviders, screen, waitFor } from "../test/test-utils";
import { UploadPage } from "./UploadPage";

const persons = [
  {
    id: "p1",
    name: "Alice",
    adjustment_account: "adj-1",
    theme_preference: "system",
  },
  {
    id: "p2",
    name: "Bob",
    adjustment_account: "adj-2",
    theme_preference: "system",
  },
];

const previewResponseAllNew = {
  new_transactions: [
    {
      date: "2026-01-15",
      merchant: "Trader Joe's",
      category: "Groceries",
      amount: -50.0,
      household: true,
      payer_percentage: 50,
    },
    {
      date: "2026-01-16",
      merchant: "Netflix",
      category: "Streaming",
      amount: -15.99,
      household: false,
      payer_percentage: 100,
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
        household: true,
        payer_percentage: 50,
      },
      existing: {
        date: "2026-01-15",
        merchant: "Old Store",
        category: "Groceries",
        amount: -50.0,
        household: true,
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

const VALID_CSV_CONTENT =
  "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n2026-01-15,Test,Cat,Chase,TEST,,-50,shared\n";

function setFileAndSubmit() {
  const fileInput = document.querySelector(
    'input[type="file"]',
  ) as HTMLInputElement;
  const file = new File([VALID_CSV_CONTENT], "test.csv", {
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

  it("renders the upload form", () => {
    renderWithProviders(<UploadPage />);
    expect(screen.getByText("Upload Transactions")).toBeInTheDocument();
    expect(
      screen.getByText("Drop your CSV here, or click to browse"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Preview CSV" }),
    ).toBeInTheDocument();
  });

  it("disables preview button when no file selected", () => {
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
    setFileAndSubmit();

    await waitFor(() => {
      expect(screen.getByText("Review Changes")).toBeInTheDocument();
    });

    expect(screen.getByText("Accept All")).toBeInTheDocument();
    expect(screen.getByText("Reject All")).toBeInTheDocument();
    expect(screen.getByText("Old Store")).toBeInTheDocument();
    // "Updated Store" appears in both the merchant label and the diff new value
    expect(screen.getAllByText("Updated Store")).toHaveLength(2);
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
              household_count: 23,
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
    expect(screen.getByText("23 household")).toBeInTheDocument();
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
    setFileAndSubmit();

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toHaveTextContent("Invalid CSV format");
    });
  });

  it("disables Preview button when CSV headers are invalid", async () => {
    renderWithProviders(<UploadPage />);

    const fileInput = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const badCsv = new File(["Name,Email\nJohn,john@test.com"], "bad.csv", {
      type: "text/csv",
    });
    fireEvent.change(fileInput, { target: { files: [badCsv] } });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Missing required columns",
      );
    });

    const previewButton = screen.getByRole("button", { name: "Preview CSV" });
    expect(previewButton).toBeDisabled();
  });

  it("clears header error when valid file is selected", async () => {
    renderWithProviders(<UploadPage />);

    const fileInput = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;

    // Select invalid file
    const badCsv = new File(["Name,Email\n"], "bad.csv", {
      type: "text/csv",
    });
    fireEvent.change(fileInput, { target: { files: [badCsv] } });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Missing required columns",
      );
    });

    // Select valid file
    const goodCsv = new File(
      [
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n2026-01-15,Test,Cat,Chase,TEST,,-50,shared\n",
      ],
      "good.csv",
      { type: "text/csv" },
    );
    fireEvent.change(fileInput, { target: { files: [goodCsv] } });

    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    const previewButton = screen.getByRole("button", { name: "Preview CSV" });
    expect(previewButton).toBeEnabled();
  });

  it("renders step indicator on initial load", () => {
    renderWithProviders(<UploadPage />);
    expect(
      screen.getByRole("navigation", { name: "Upload progress" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Select file")).toBeInTheDocument();
    expect(screen.getByText("Preview")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("shows confirmed card with stats and animated check after upload", async () => {
    server.use(
      http.post("/api/v1/uploads/preview", () =>
        HttpResponse.json(previewResponseAllNew),
      ),
      http.post("/api/v1/uploads/", () =>
        HttpResponse.json(
          {
            upload_id: "u1",
            filename: "test.csv",
            new_count: 2,
            updated_count: 0,
            skipped_count: 0,
            unmapped_categories: [],
          },
          { status: 201 },
        ),
      ),
    );

    renderWithProviders(<UploadPage />);
    setFileAndSubmit();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Confirm Import" }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirm Import" }));
    await waitFor(() => {
      expect(screen.getByText("Upload Complete")).toBeInTheDocument();
    });

    expect(document.querySelector(".animated-check")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("New")).toBeInTheDocument();
  });

  it("shows Review transactions link with correct month", async () => {
    server.use(
      http.post("/api/v1/uploads/preview", () =>
        HttpResponse.json(previewResponseAllNew),
      ),
      http.post("/api/v1/uploads/", () =>
        HttpResponse.json(
          {
            upload_id: "u1",
            filename: "test.csv",
            new_count: 2,
            updated_count: 0,
            skipped_count: 0,
            unmapped_categories: [],
          },
          { status: 201 },
        ),
      ),
    );

    renderWithProviders(<UploadPage />);
    setFileAndSubmit();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Confirm Import" }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirm Import" }));
    await waitFor(() => {
      expect(screen.getByText("Review transactions")).toBeInTheDocument();
    });

    const link = screen.getByText("Review transactions").closest("a");
    expect(link).toHaveAttribute("href", "/transactions?year=2026&month=1");
  });

  it("shows partner upload prompt when partner hasn't uploaded", async () => {
    server.use(
      http.post("/api/v1/uploads/preview", () =>
        HttpResponse.json(previewResponseAllNew),
      ),
      http.post("/api/v1/uploads/", () =>
        HttpResponse.json(
          {
            upload_id: "u1",
            filename: "test.csv",
            new_count: 2,
            updated_count: 0,
            skipped_count: 0,
            unmapped_categories: [],
          },
          { status: 201 },
        ),
      ),
    );

    renderWithProviders(<UploadPage />);
    setFileAndSubmit();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Confirm Import" }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirm Import" }));
    await waitFor(() => {
      expect(screen.getByText("Upload Complete")).toBeInTheDocument();
    });

    expect(
      screen.getByRole("button", { name: /Upload Bob's CSV/ }),
    ).toBeInTheDocument();
  });

  it("hides partner prompt when partner has uploaded for same month", async () => {
    server.use(
      http.get("/api/v1/uploads/history", () =>
        HttpResponse.json({
          entries: [
            {
              upload_id: "u2",
              person_id: "p2",
              person_name: "Bob",
              filename: "jan-2026.csv",
              uploaded_at: new Date().toISOString(),
              transaction_count: 30,
              household_count: 15,
              date_range_start: "2026-01-01",
              date_range_end: "2026-01-31",
            },
          ],
        }),
      ),
      http.post("/api/v1/uploads/preview", () =>
        HttpResponse.json(previewResponseAllNew),
      ),
      http.post("/api/v1/uploads/", () =>
        HttpResponse.json(
          {
            upload_id: "u1",
            filename: "test.csv",
            new_count: 2,
            updated_count: 0,
            skipped_count: 0,
            unmapped_categories: [],
          },
          { status: 201 },
        ),
      ),
    );

    renderWithProviders(<UploadPage />);
    setFileAndSubmit();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Confirm Import" }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirm Import" }));
    await waitFor(() => {
      expect(screen.getByText("Upload Complete")).toBeInTheDocument();
    });

    expect(
      screen.queryByRole("button", { name: /Upload Bob's CSV/ }),
    ).not.toBeInTheDocument();
  });

  it("renders multi-line server errors as a list", async () => {
    server.use(
      http.post("/api/v1/uploads/preview", () =>
        HttpResponse.json(
          {
            error: {
              message:
                'Row 2 (Starbucks): invalid amount "abc"\nRow 5 (Amazon): invalid date "2026-13-01"',
            },
          },
          { status: 422 },
        ),
      ),
    );

    renderWithProviders(<UploadPage />);
    setFileAndSubmit();

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toHaveTextContent("Row 2 (Starbucks)");
      expect(alert).toHaveTextContent("Row 5 (Amazon)");
    });

    const listItems = screen.getByRole("alert").querySelectorAll("li");
    expect(listItems).toHaveLength(2);
  });
});
