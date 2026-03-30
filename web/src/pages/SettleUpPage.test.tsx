import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { useIdentityStore } from "@/lib/identity";
import { server } from "@/test/server";
import { renderWithProviders, screen, waitFor } from "../test/test-utils";
import { SettleUpPage } from "./SettleUpPage";

const persons = [
  {
    id: "p1",
    name: "Alice",
    adjustment_account: "",
    theme_preference: "system",
  },
  { id: "p2", name: "Bob", adjustment_account: "", theme_preference: "system" },
];

const settleUpResponse = {
  year: 2026,
  month: 3,
  owed: { amount: 50.0, from_person_id: "p2", to_person_id: "p1" },
  recorded_settlements: [],
  remaining_balance: 50.0,
  upload_statuses: [
    {
      person_id: "p1",
      person_name: "Alice",
      has_uploaded: true,
      upload_count: 1,
    },
    {
      person_id: "p2",
      person_name: "Bob",
      has_uploaded: true,
      upload_count: 1,
    },
  ],
  persons: [
    { id: "p1", name: "Alice" },
    { id: "p2", name: "Bob" },
  ],
  is_finalized: false,
  finalized_at: null,
  transaction_count: 5,
  latest_transaction_month: { year: 2026, month: 3 },
};

const emptyResponse = {
  year: 2026,
  month: 3,
  owed: { amount: 0.0, from_person_id: "p1", to_person_id: "p2" },
  recorded_settlements: [],
  remaining_balance: 0.0,
  upload_statuses: [
    {
      person_id: "p1",
      person_name: "Alice",
      has_uploaded: false,
      upload_count: 0,
    },
    {
      person_id: "p2",
      person_name: "Bob",
      has_uploaded: false,
      upload_count: 0,
    },
  ],
  persons: [
    { id: "p1", name: "Alice" },
    { id: "p2", name: "Bob" },
  ],
  is_finalized: false,
  finalized_at: null,
  transaction_count: 0,
  latest_transaction_month: null,
};

const emptyWithPriorDataResponse = {
  ...emptyResponse,
  latest_transaction_month: { year: 2026, month: 2 },
};

const allSettledResponse = {
  ...settleUpResponse,
  owed: { amount: 0.0, from_person_id: "p1", to_person_id: "p2" },
  remaining_balance: 0.0,
  transaction_count: 5,
};

describe("SettleUpPage", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: "p1" });
    server.use(
      http.get("/api/v1/persons/", () => HttpResponse.json(persons)),
      http.get("/api/v1/settle-up", () => HttpResponse.json(settleUpResponse)),
    );
  });

  it("shows owed amount when balance exists", async () => {
    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText(/owes/)).toBeInTheDocument();
      expect(screen.getByText("$50.00")).toBeInTheDocument();
    });
  });

  it("shows empty state when no transactions", async () => {
    server.use(
      http.get("/api/v1/settle-up", () => HttpResponse.json(emptyResponse)),
    );

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/No household transactions for/),
      ).toBeInTheDocument();
      expect(screen.getByText("Upload CSV")).toBeInTheDocument();
    });

    expect(screen.queryByText("All settled!")).not.toBeInTheDocument();
    expect(screen.queryByText(/View /)).not.toBeInTheDocument();
  });

  it("shows link to latest month when prior data exists", async () => {
    server.use(
      http.get("/api/v1/settle-up", () =>
        HttpResponse.json(emptyWithPriorDataResponse),
      ),
    );

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/No household transactions for/),
      ).toBeInTheDocument();
      expect(screen.getByText("Upload CSV")).toBeInTheDocument();
      expect(screen.getByText("View February 2026")).toBeInTheDocument();
    });
  });

  it("shows 'All settled!' when transactions exist but balance is zero", async () => {
    server.use(
      http.get("/api/v1/settle-up", () =>
        HttpResponse.json(allSettledResponse),
      ),
    );

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText("All settled!")).toBeInTheDocument();
    });

    expect(
      screen.queryByText(/No household transactions for/),
    ).not.toBeInTheDocument();
  });

  it("shows upload statuses in empty state", async () => {
    server.use(
      http.get("/api/v1/settle-up", () => HttpResponse.json(emptyResponse)),
    );

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getAllByText("not yet")).toHaveLength(2);
    });
  });
});
