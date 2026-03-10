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

const previewResponse = {
  transactions: [
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
  total_count: 2,
  shared_count: 1,
  personal_count: 1,
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
  const form = fileInput.closest("form")!;
  fireEvent.submit(form);
}

describe("UploadPage", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: "p1" });
  });

  it("renders the upload form", () => {
    renderWithProviders(<UploadPage />);
    expect(screen.getByText("Upload Transactions")).toBeInTheDocument();
    expect(screen.getByLabelText("Who are you?")).toBeInTheDocument();
    expect(screen.getByLabelText("Month")).toBeInTheDocument();
    expect(screen.getByLabelText("Year")).toBeInTheDocument();
    expect(screen.getByLabelText("Monarch CSV")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview" })).toBeInTheDocument();
  });

  it("disables preview button when no person selected", () => {
    useIdentityStore.setState({ currentPersonId: null });
    renderWithProviders(<UploadPage />);
    const button = screen.getByRole("button", { name: "Preview" });
    expect(button).toBeDisabled();
  });

  it("shows filter pills with aria-pressed after preview", async () => {
    server.use(
      http.post("/api/v1/uploads/preview", () =>
        HttpResponse.json(previewResponse),
      ),
    );

    renderWithProviders(<UploadPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("Who are you?")).toBeInTheDocument();
    });

    setFileAndSubmit();

    await waitFor(() => {
      expect(screen.getByText("All (2)")).toBeInTheDocument();
    });

    const allButton = screen.getByText("All (2)");
    const sharedButton = screen.getByText("Shared (1)");
    expect(allButton).toHaveAttribute("aria-pressed", "true");
    expect(sharedButton).toHaveAttribute("aria-pressed", "false");
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
      expect(screen.getByLabelText("Who are you?")).toBeInTheDocument();
    });

    setFileAndSubmit();

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toHaveTextContent("Invalid CSV format");
    });
  });
});
