import { describe, expect, it, vi } from "vitest";
import type {
  LedgerMonthResponse,
  LedgerSettlementResponse,
  PayerGroupSplitSummaryResponse,
  PayerSplitSummaryResponse,
  SettleUpDataResponse,
} from "@/api/generated/model";
import { makeLedgerMonth, makeLedgerSettlement } from "@/test/ledger-fixtures";
import { renderWithProviders, screen, userEvent } from "@/test/test-utils";
import { SettleUpAuditTable } from "./SettleUpAuditTable";

const ALICE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const BOB_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";

const PERSON_NAMES = new Map<string, string>([
  [ALICE_ID, "Alice"],
  [BOB_ID, "Bob"],
]);

function makePayerSplit(
  overrides: Partial<PayerSplitSummaryResponse>,
): PayerSplitSummaryResponse {
  return {
    payer_person_id: ALICE_ID,
    fronted: 0,
    their_share: 0,
    partner_share: 0,
    transaction_count: 0,
    ...overrides,
  };
}

function makeGroupSplit(
  overrides: Partial<PayerGroupSplitSummaryResponse>,
): PayerGroupSplitSummaryResponse {
  return {
    payer_person_id: ALICE_ID,
    group_id: "g1",
    group_name: "Food & Dining",
    fronted: 0,
    their_share: 0,
    partner_share: 0,
    transaction_count: 0,
    categories: ["Dining Out"],
    ...overrides,
  };
}

// Portions default to one full-amount slice at the viewed month (2026-03).
function makeSettlement(
  overrides: Partial<LedgerSettlementResponse>,
): LedgerSettlementResponse {
  const amount = overrides.amount ?? 0;
  return makeLedgerSettlement({
    id: "s1",
    amount,
    from_person_id: ALICE_ID,
    to_person_id: BOB_ID,
    settled_at: "2026-04-22T00:00:00Z",
    created_at: "2026-04-22T00:00:00Z",
    portions: [{ year: 2026, month: 3, amount }],
    ...overrides,
  });
}

function makeMonth(
  overrides: Partial<LedgerMonthResponse>,
): LedgerMonthResponse {
  return makeLedgerMonth({ year: 2026, month: 3, ...overrides });
}

function makeData(
  overrides: Partial<SettleUpDataResponse> = {},
): SettleUpDataResponse {
  const splits = overrides.payer_splits ?? [
    makePayerSplit({ payer_person_id: ALICE_ID }),
    makePayerSplit({ payer_person_id: BOB_ID }),
  ];
  return {
    year: 2026,
    month: 3,
    years: [],
    months: [],
    settlements: [],
    upload_statuses: [],
    persons: [
      { id: ALICE_ID, name: "Alice" },
      { id: BOB_ID, name: "Bob" },
    ],
    is_finalized: false,
    finalized_at: null,
    transaction_count: splits.reduce((s, p) => s + p.transaction_count, 0),
    latest_transaction_month: null,
    finalization_warnings: [],
    payer_splits: splits,
    payer_group_splits: [],
    ...overrides,
  };
}

async function expandLedger() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: /show ledger/i }));
}

describe("SettleUpAuditTable", () => {
  it("renders nothing when both splits and settlements are empty", () => {
    const { container } = renderWithProviders(
      <SettleUpAuditTable data={makeData()} personNames={PERSON_NAMES} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("hides the ledger by default and reveals it via 'Show ledger'", async () => {
    const data = makeData({
      payer_splits: [
        makePayerSplit({
          payer_person_id: ALICE_ID,
          fronted: 100,
          their_share: 50,
          partner_share: 50,
          transaction_count: 1,
        }),
        makePayerSplit({ payer_person_id: BOB_ID }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );

    expect(screen.queryByRole("table")).not.toBeInTheDocument();

    await expandLedger();

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("Alice's bills")).toBeInTheDocument();
  });

  it("states the API's month balance in both the Summary and the Total row", async () => {
    // The month entry says Bob owes Alice $24.11 — the same entry the month
    // row renders, so the two surfaces can never diverge.
    const data = makeData({
      payer_splits: [
        makePayerSplit({
          payer_person_id: ALICE_ID,
          fronted: 3913.78,
          their_share: 1956.89,
          partner_share: 1956.89,
          transaction_count: 12,
        }),
        makePayerSplit({ payer_person_id: BOB_ID }),
      ],
      months: [
        makeMonth({
          balance: {
            amount: 24.11,
            from_person_id: BOB_ID,
            to_person_id: ALICE_ID,
          },
          status: "partially_settled",
        }),
      ],
      settlements: [
        makeSettlement({
          amount: 1981,
          from_person_id: BOB_ID,
          to_person_id: ALICE_ID,
          method: "venmo",
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );

    expect(screen.getByText(/Bob owes Alice \$24\.11/)).toBeInTheDocument();

    await expandLedger();

    // + in Net favors persons[0] (Alice); Bob owing Alice renders positive.
    const totalRow = screen.getByText("Total").closest("tr") as HTMLElement;
    expect(totalRow.textContent).toContain("+$24.11");
  });

  it("renders bills with positive Net when persons[0] paid", async () => {
    const data = makeData({
      payer_splits: [
        makePayerSplit({
          payer_person_id: ALICE_ID,
          fronted: 100,
          their_share: 50,
          partner_share: 50,
          transaction_count: 1,
        }),
        makePayerSplit({ payer_person_id: BOB_ID }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );
    await expandLedger();

    const row = screen.getByText("Alice's bills").closest("tr") as HTMLElement;
    expect(row.textContent).toContain("+$50.00");
  });

  it("renders bills with negative Net when persons[1] paid", async () => {
    const data = makeData({
      payer_splits: [
        makePayerSplit({ payer_person_id: ALICE_ID }),
        makePayerSplit({
          payer_person_id: BOB_ID,
          fronted: 80,
          their_share: 40,
          partner_share: 40,
          transaction_count: 2,
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );
    await expandLedger();

    const row = screen.getByText("Bob's bills").closest("tr") as HTMLElement;
    expect(row.textContent).toContain("−$40.00");
  });

  it("settlement Net is this month's portion, signed by sender", async () => {
    // A $500 catch-up lump: only its $300 March portion counts on the March
    // drill-down; the April slice belongs to April's.
    const data = makeData({
      payer_splits: [
        makePayerSplit({
          payer_person_id: ALICE_ID,
          fronted: 600,
          their_share: 300,
          partner_share: 300,
          transaction_count: 1,
        }),
        makePayerSplit({ payer_person_id: BOB_ID }),
      ],
      settlements: [
        makeSettlement({
          amount: 500,
          from_person_id: BOB_ID,
          to_person_id: ALICE_ID,
          method: "venmo",
          portions: [
            { year: 2026, month: 3, amount: 300 },
            { year: 2026, month: 4, amount: 200 },
          ],
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );
    await expandLedger();

    const row = screen
      .getByText(/Bob → Alice via venmo/)
      .closest("tr") as HTMLElement;
    expect(row.textContent).toContain("−$300.00");
    expect(row.textContent).not.toContain("$500.00");
  });

  it("ignores settlements whose portions never touch the viewed month", () => {
    const data = makeData({
      settlements: [
        makeSettlement({
          amount: 100,
          portions: [{ year: 2026, month: 7, amount: 100 }],
        }),
      ],
    });

    const { container } = renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("settlement rows have dashed Amount, Txns, and share cells", async () => {
    const data = makeData({
      settlements: [
        makeSettlement({
          amount: 10,
          from_person_id: BOB_ID,
          to_person_id: ALICE_ID,
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );
    await expandLedger();

    const row = screen.getByText(/Bob → Alice/).closest("tr") as HTMLElement;
    const dashes = row.querySelectorAll("td span");
    expect(dashes.length).toBeGreaterThanOrEqual(4);
  });

  it("by-category view shows '{group} · {payer}' rows", async () => {
    const user = userEvent.setup();
    const data = makeData({
      payer_splits: [
        makePayerSplit({
          payer_person_id: ALICE_ID,
          fronted: 100,
          their_share: 50,
          partner_share: 50,
          transaction_count: 1,
        }),
        makePayerSplit({ payer_person_id: BOB_ID }),
      ],
      payer_group_splits: [
        makeGroupSplit({
          payer_person_id: ALICE_ID,
          group_name: "Food & Dining",
          fronted: 100,
          their_share: 50,
          partner_share: 50,
          transaction_count: 1,
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );

    await expandLedger();
    await user.click(screen.getByRole("radio", { name: /by category/i }));

    expect(screen.getByText("Food & Dining · Alice")).toBeInTheDocument();
  });

  it("copies the table as TSV + HTML when the Copy button is clicked", async () => {
    const user = userEvent.setup();
    const writeMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { write: writeMock, writeText: vi.fn() },
    });
    // jsdom doesn't ship ClipboardItem; provide a minimal stub.
    type ClipboardItemCtor = new (
      data: Record<string, Blob>,
    ) => { types: string[]; data: Record<string, Blob> };
    const ClipboardItemStub: ClipboardItemCtor = function (
      this: { types: string[]; data: Record<string, Blob> },
      data: Record<string, Blob>,
    ) {
      this.types = Object.keys(data);
      this.data = data;
    } as unknown as ClipboardItemCtor;
    (window as unknown as { ClipboardItem: ClipboardItemCtor }).ClipboardItem =
      ClipboardItemStub;

    const data = makeData({
      payer_splits: [
        makePayerSplit({
          payer_person_id: ALICE_ID,
          fronted: 100,
          their_share: 50,
          partner_share: 50,
          transaction_count: 1,
        }),
        makePayerSplit({ payer_person_id: BOB_ID }),
      ],
      // The Total row's Net renders the served month balance.
      months: [
        makeMonth({
          balance: {
            amount: 50,
            from_person_id: BOB_ID,
            to_person_id: ALICE_ID,
          },
          status: "carried_forward",
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );

    await user.click(screen.getByRole("button", { name: /show ledger/i }));
    await user.click(screen.getByRole("button", { name: /copy/i }));

    expect(writeMock).toHaveBeenCalledOnce();
    const items = writeMock.mock.calls[0][0] as Array<{
      types: string[];
      data: Record<string, Blob>;
    }>;
    expect(items[0].types).toEqual(["text/plain", "text/html"]);

    const tsvText = await items[0].data["text/plain"].text();
    expect(tsvText).toContain("Activity\tAmount\tTxns");
    expect(tsvText).toContain("Alice's bills\t100.00\t1\t50.00\t50.00\t50.00");
    expect(tsvText).toContain("Total\t100.00\t1\t50.00\t50.00\t50.00");

    expect(screen.getByText("Copied")).toBeInTheDocument();
  });

  it("each Activity cell is a link to the Transactions page with appropriate filters", async () => {
    const data = makeData({
      payer_splits: [
        makePayerSplit({
          payer_person_id: ALICE_ID,
          fronted: 100,
          their_share: 50,
          partner_share: 50,
          transaction_count: 1,
        }),
        makePayerSplit({ payer_person_id: BOB_ID }),
      ],
      settlements: [
        makeSettlement({
          amount: 10,
          from_person_id: ALICE_ID,
          to_person_id: BOB_ID,
          method: "venmo",
          settled_at: "2026-04-26T00:00:00Z",
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );

    await expandLedger();

    // Bill row links to Transactions filtered by year/month/payer. It must NOT
    // pin scope=household — audit rows include non-household settlement splits
    // (spotted / personal-split) that a household filter would drop.
    const billLink = screen.getByRole("link", { name: "Alice's bills" });
    expect(billLink.getAttribute("href")).toContain("/transactions?");
    expect(billLink.getAttribute("href")).toContain("year=2026");
    expect(billLink.getAttribute("href")).toContain("month=3");
    expect(billLink.getAttribute("href")).toContain(`payer=${ALICE_ID}`);
    expect(billLink.getAttribute("href")).not.toContain("scope=household");

    // With no linked transactions the settlement row falls back to its
    // attributed month (waivers, manual records) — not the settled_at
    // recording moment, which here is April.
    const settlementLink = screen.getByRole("link", {
      name: /Alice → Bob via venmo/,
    });
    expect(settlementLink.getAttribute("href")).toContain("year=2026");
    expect(settlementLink.getAttribute("href")).toContain("month=3");
    expect(settlementLink.getAttribute("href")).toContain("settlement=1");
  });

  it("settlement rows link via the earliest linked transaction's date, not settled_at", async () => {
    const data = makeData({
      settlements: [
        makeSettlement({
          amount: 10,
          from_person_id: ALICE_ID,
          to_person_id: BOB_ID,
          method: "venmo",
          // Recorded in May; the transfers themselves straddle March/April.
          settled_at: "2026-05-01T02:00:00Z",
          linked_transactions: [
            {
              id: "lt1",
              date: "2026-04-02",
              merchant: "Venmo",
              amount: 10,
              payer_person_id: BOB_ID,
            },
            {
              id: "lt2",
              date: "2026-03-31",
              merchant: "Venmo",
              amount: -10,
              payer_person_id: ALICE_ID,
            },
          ],
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );

    await expandLedger();

    const settlementLink = screen.getByRole("link", {
      name: /Alice → Bob via venmo/,
    });
    expect(settlementLink.getAttribute("href")).toContain("year=2026");
    expect(settlementLink.getAttribute("href")).toContain("month=3");
    expect(settlementLink.getAttribute("href")).toContain("settlement=1");
  });

  it("shows empty-state row when there are no split bills", async () => {
    const data = makeData({
      settlements: [
        makeSettlement({
          amount: 10,
          from_person_id: BOB_ID,
          to_person_id: ALICE_ID,
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );

    await expandLedger();

    expect(
      screen.getByText("No split bills for this period yet."),
    ).toBeInTheDocument();
  });

  describe("balance narrative", () => {
    it("describes both payers, the settlement, and the resulting balance", () => {
      const data = makeData({
        payer_splits: [
          makePayerSplit({
            payer_person_id: ALICE_ID,
            fronted: 200,
            their_share: 100,
            partner_share: 100,
            transaction_count: 2,
          }),
          makePayerSplit({
            payer_person_id: BOB_ID,
            fronted: 50,
            their_share: 25,
            partner_share: 25,
            transaction_count: 1,
          }),
        ],
        months: [
          makeMonth({
            balance: {
              amount: 45,
              from_person_id: BOB_ID,
              to_person_id: ALICE_ID,
            },
            status: "partially_settled",
          }),
        ],
        settlements: [
          makeSettlement({
            amount: 30,
            from_person_id: BOB_ID,
            to_person_id: ALICE_ID,
            method: "venmo",
          }),
        ],
      });

      renderWithProviders(
        <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
      );

      const narrative = screen.getByText(/Alice fronted/);
      expect(narrative.textContent).toContain(
        "Alice fronted $200.00 across 2 bills",
      );
      expect(narrative.textContent).toContain(
        "Bob fronted $50.00 across 1 bill",
      );
      expect(narrative.textContent).toContain("one venmo transfer");
      expect(narrative.textContent).toContain("Bob owes Alice $45.00");
    });

    it("says 'the balance is settled' when the month balance is null", () => {
      const data = makeData({
        payer_splits: [
          makePayerSplit({
            payer_person_id: ALICE_ID,
            fronted: 100,
            their_share: 50,
            partner_share: 50,
            transaction_count: 1,
          }),
          makePayerSplit({ payer_person_id: BOB_ID }),
        ],
        months: [makeMonth({ balance: null, status: "settled" })],
      });

      renderWithProviders(
        <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
      );

      expect(screen.getByText(/the balance is settled/)).toBeInTheDocument();
    });

    it("describes a waiver as 'a waiver'", () => {
      const data = makeData({
        settlements: [
          makeSettlement({
            amount: 25,
            from_person_id: BOB_ID,
            to_person_id: ALICE_ID,
            is_waived: true,
          }),
        ],
      });

      renderWithProviders(
        <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
      );

      expect(screen.getByText(/After a waiver/)).toBeInTheDocument();
    });

    it("counts multiple settlements", () => {
      const data = makeData({
        settlements: [
          makeSettlement({
            id: "s1",
            amount: 10,
            from_person_id: BOB_ID,
            to_person_id: ALICE_ID,
          }),
          makeSettlement({
            id: "s2",
            amount: 20,
            from_person_id: BOB_ID,
            to_person_id: ALICE_ID,
          }),
        ],
      });

      renderWithProviders(
        <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
      );

      expect(screen.getByText(/After 2 settlements/)).toBeInTheDocument();
    });
  });
});
