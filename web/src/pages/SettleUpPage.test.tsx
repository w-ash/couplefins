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
    chat_voice: "fiona",
  },
  {
    id: "p2",
    name: "Bob",
    adjustment_account: "",
    theme_preference: "system",
    chat_voice: "fiona",
  },
];

const settleUpResponse = {
  year: 2026,
  month: 3,
  owed: { amount: 50.0, from_person_id: "p2", to_person_id: "p1" },
  net_position: { amount: 50.0, from_person_id: "p2", to_person_id: "p1" },
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
  finalization_warnings: [],
  payer_splits: [],
  payer_group_splits: [],
};

const emptyResponse = {
  year: 2026,
  month: 3,
  owed: { amount: 0.0, from_person_id: "p1", to_person_id: "p2" },
  net_position: null,
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
  finalization_warnings: [],
  payer_splits: [],
  payer_group_splits: [],
};

const emptyWithPriorDataResponse = {
  ...emptyResponse,
  latest_transaction_month: { year: 2026, month: 2 },
};

const allSettledResponse = {
  ...settleUpResponse,
  owed: { amount: 0.0, from_person_id: "p1", to_person_id: "p2" },
  net_position: null,
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

  it("renders the audit table when there are split aggregates or settlements", async () => {
    const populated = {
      ...settleUpResponse,
      payer_splits: [
        {
          payer_person_id: "p1",
          fronted: 100,
          their_share: 50,
          partner_share: 50,
          transaction_count: 1,
        },
        {
          payer_person_id: "p2",
          fronted: 0,
          their_share: 0,
          partner_share: 0,
          transaction_count: 0,
        },
      ],
    };
    server.use(
      http.get("/api/v1/settle-up", () => HttpResponse.json(populated)),
    );

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText("Showing the work")).toBeInTheDocument();
    });
    expect(
      screen.getByRole("button", { name: /show ledger/i }),
    ).toBeInTheDocument();
  });

  it("shows empty state when no transactions", async () => {
    server.use(
      http.get("/api/v1/settle-up", () => HttpResponse.json(emptyResponse)),
    );

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/No transactions to settle for/),
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
        screen.getByText(/No transactions to settle for/),
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
      screen.queryByText(/No transactions to settle for/),
    ).not.toBeInTheDocument();
  });

  it("keeps the link UI available after balance reaches zero", async () => {
    // Original gross balance still exposed via `owed` even when net_position is null
    const settledWithGross = {
      ...allSettledResponse,
      owed: { amount: 50.0, from_person_id: "p2", to_person_id: "p1" },
    };
    server.use(
      http.get("/api/v1/settle-up", () => HttpResponse.json(settledWithGross)),
    );

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText("All settled!")).toBeInTheDocument();
    });

    // Link UI must remain so the user can record additional settlements
    expect(screen.getByText("Link bank transactions")).toBeInTheDocument();
  });

  it("shows link UI in reversed direction when balance is overpaid", async () => {
    const overpaidResponse = {
      ...settleUpResponse,
      owed: { amount: 50.0, from_person_id: "p2", to_person_id: "p1" },
      net_position: { amount: 30.0, from_person_id: "p1", to_person_id: "p2" },
      remaining_balance: 30.0,
    };
    server.use(
      http.get("/api/v1/settle-up", () => HttpResponse.json(overpaidResponse)),
    );

    renderWithProviders(<SettleUpPage />);

    await waitFor(() => {
      expect(screen.getByText("Link bank transactions")).toBeInTheDocument();
    });
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
