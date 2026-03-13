import { fireEvent } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
} from "vitest";
import { useIdentityStore } from "@/lib/identity";
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

const server = setupServer(
  http.get("/api/v1/persons/", () => HttpResponse.json(persons)),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function setFileAndSubmit() {
  const fileInput = screen.getByLabelText("Monarch CSV") as HTMLInputElement;
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
  });

  it("renders the upload form without month/year", () => {
    renderWithProviders(<UploadPage />);
    expect(screen.getByText("Upload Transactions")).toBeInTheDocument();
    expect(screen.getByText("Who are you?")).toBeInTheDocument();
    expect(screen.queryByLabelText("Month")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Year")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Monarch CSV")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview" })).toBeInTheDocument();
  });

  it("disables preview button when no person selected", () => {
    useIdentityStore.setState({ currentPersonId: null });
    renderWithProviders(<UploadPage />);
    const button = screen.getByRole("button", { name: "Preview" });
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
        screen.getByText("All transactions already imported. Nothing to do."),
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
