import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/server";
import { renderWithProviders, screen, waitFor } from "@/test/test-utils";
import { UploadHistory } from "./UploadHistory";

const historyEntries = [
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
  {
    upload_id: "u2",
    person_id: "p2",
    person_name: "Bob",
    filename: "february-export.csv",
    uploaded_at: new Date(Date.now() - 5 * 86400000).toISOString(),
    transaction_count: 38,
    household_count: 19,
    date_range_start: "2026-02-01",
    date_range_end: "2026-02-28",
  },
];

describe("UploadHistory", () => {
  it("renders entries with person names and stats", async () => {
    server.use(
      http.get("/api/v1/uploads/history", () =>
        HttpResponse.json({ entries: historyEntries }),
      ),
    );

    renderWithProviders(<UploadHistory />);

    await waitFor(() => {
      expect(screen.getByText("Past Uploads")).toBeInTheDocument();
    });
    expect(screen.getByText("march-2026.csv")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("47 transactions")).toBeInTheDocument();
    expect(screen.getByText("23 household")).toBeInTheDocument();
    expect(screen.getByText("february-export.csv")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
    expect(screen.getByText("38 transactions")).toBeInTheDocument();
  });

  it("renders empty state when no uploads", async () => {
    server.use(
      http.get("/api/v1/uploads/history", () =>
        HttpResponse.json({ entries: [] }),
      ),
    );

    renderWithProviders(<UploadHistory />);

    await waitFor(() => {
      expect(screen.getByText("No uploads yet")).toBeInTheDocument();
    });
    expect(screen.queryByText("Past Uploads")).not.toBeInTheDocument();
  });

  it("shows loading state", () => {
    server.use(
      http.get("/api/v1/uploads/history", () => {
        return new Promise(() => {});
      }),
    );

    renderWithProviders(<UploadHistory />);

    expect(screen.getByText("Loading upload history...")).toBeInTheDocument();
  });

  it("shows 'show older' button when more than 6 entries", async () => {
    const manyEntries = Array.from({ length: 8 }, (_, i) => ({
      upload_id: `u${i}`,
      person_id: i % 2 === 0 ? "p1" : "p2",
      person_name: i % 2 === 0 ? "Alice" : "Bob",
      filename: `upload-${i}.csv`,
      uploaded_at: new Date(Date.now() - i * 86400000).toISOString(),
      transaction_count: 10 + i,
      household_count: 5 + i,
      date_range_start: "2026-01-01",
      date_range_end: "2026-01-31",
    }));

    server.use(
      http.get("/api/v1/uploads/history", () =>
        HttpResponse.json({ entries: manyEntries }),
      ),
    );

    renderWithProviders(<UploadHistory />);

    await waitFor(() => {
      expect(screen.getByText("Past Uploads")).toBeInTheDocument();
    });

    // Only 6 visible initially
    expect(screen.queryByText("upload-7.csv")).not.toBeInTheDocument();
    expect(screen.getByText("Show older uploads (2 more)")).toBeInTheDocument();
  });
});
