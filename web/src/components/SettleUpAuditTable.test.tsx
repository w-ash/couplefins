import { describe, expect, it, vi } from "vitest";
import type {
  PayerGroupSplitSummaryResponse,
  PayerSplitSummaryResponse,
  SettlementResponse,
  SettleUpDataResponse,
} from "@/api/generated/model";
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

function makeSettlement(
  overrides: Partial<SettlementResponse>,
): SettlementResponse {
  return {
    id: "s1",
    year: 2026,
    month: 3,
    amount: 0,
    from_person_id: ALICE_ID,
    to_person_id: BOB_ID,
    method: null,
    is_waived: false,
    notes: "",
    settled_at: "2026-04-22T00:00:00Z",
    created_at: "2026-04-22T00:00:00Z",
    linked_transaction_ids: [],
    linked_transactions: [],
    ...overrides,
  };
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
    owed: null,
    recorded_settlements: [],
    outstanding: null,
    outstanding_span: null,
    ledger_months: [],
    all_settlements: [],
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

    expect(screen.queryByText("Activity")).not.toBeInTheDocument();
    expect(screen.queryByText("Alice's bills")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /copy/i }),
    ).not.toBeInTheDocument();

    await expandLedger();

    expect(screen.getByText("Activity")).toBeInTheDocument();
    expect(screen.getByText("Alice's bills")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /copy/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /hide ledger/i }),
    ).toBeInTheDocument();
  });

  it("renders the six-column header with person names", async () => {
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

    expect(screen.getByText("Activity")).toBeInTheDocument();
    expect(screen.getByText("Amount")).toBeInTheDocument();
    expect(screen.getByText("Txns")).toBeInTheDocument();
    expect(screen.getByText("Alice's share")).toBeInTheDocument();
    expect(screen.getByText("Bob's share")).toBeInTheDocument();
    expect(screen.getByText("Net")).toBeInTheDocument();
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

    const aliceRow = screen.getByText("Alice's bills").closest("tr");
    expect(aliceRow?.textContent).toContain("+$50.00");
    const totalRow = screen.getByText("Total").closest("tr") as HTMLElement;
    expect(totalRow.textContent).toContain("+$50.00");
  });

  it("renders bills with negative Net when persons[1] paid", async () => {
    const data = makeData({
      payer_splits: [
        makePayerSplit({ payer_person_id: ALICE_ID }),
        makePayerSplit({
          payer_person_id: BOB_ID,
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

    const bobRow = screen.getByText("Bob's bills").closest("tr");
    expect(bobRow?.textContent).toContain("−$50.00");
    const totalRow = screen.getByText("Total").closest("tr") as HTMLElement;
    expect(totalRow.textContent).toContain("−$50.00");
  });

  it("settlement Net follows sender direction", async () => {
    // Alice paid $100 50/50 → Net +$50 toward Alice.
    // Alice → Bob $30 → Net +$30 toward Alice (Alice paid down a debt).
    // Total Net = +$80 → Alice is up $80.
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
      recorded_settlements: [
        makeSettlement({
          amount: 30,
          from_person_id: ALICE_ID,
          to_person_id: BOB_ID,
          method: "venmo",
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );

    await expandLedger();

    const totalRow = screen.getByText("Total").closest("tr") as HTMLElement;
    expect(totalRow.textContent).toContain("+$80.00");
  });

  it("Total row sums each share column and the Net column", async () => {
    // Bills:
    //   Alice paid $100 50/50 → her share $50, Bob's $50, Net +$50
    //   Bob paid $200 50/50 → his share $100, Alice's $100, Net −$100
    // Settlements:
    //   Alice → Bob $40 → Net +$40
    //
    // Share totals: Alice $50 + $100 = $150, Bob $50 + $100 = $150
    // Net total: +50 - 100 + 40 = −$10 → Bob is up $10
    const data = makeData({
      payer_splits: [
        makePayerSplit({
          payer_person_id: ALICE_ID,
          fronted: 100,
          their_share: 50,
          partner_share: 50,
          transaction_count: 1,
        }),
        makePayerSplit({
          payer_person_id: BOB_ID,
          fronted: 200,
          their_share: 100,
          partner_share: 100,
          transaction_count: 2,
        }),
      ],
      recorded_settlements: [
        makeSettlement({
          amount: 40,
          from_person_id: ALICE_ID,
          to_person_id: BOB_ID,
          method: "venmo",
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );

    await expandLedger();

    const totalRow = screen.getByText("Total").closest("tr") as HTMLElement;
    expect(totalRow.textContent).toContain("$150.00");
    expect(totalRow.textContent).toContain("−$10.00");
  });

  it("Net total is zero when bills and settlements offset exactly", async () => {
    const data = makeData({
      payer_splits: [
        makePayerSplit({ payer_person_id: ALICE_ID }),
        makePayerSplit({
          payer_person_id: BOB_ID,
          fronted: 100,
          their_share: 50,
          partner_share: 50,
          transaction_count: 1,
        }),
      ],
      recorded_settlements: [
        makeSettlement({
          amount: 50,
          from_person_id: ALICE_ID,
          to_person_id: BOB_ID,
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );

    await expandLedger();

    const totalRow = screen.getByText("Total").closest("tr") as HTMLElement;
    expect(totalRow.textContent).toContain("$0.00");
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

    await user.click(screen.getByRole("button", { name: /show ledger/i }));
    await user.click(screen.getByRole("radio", { name: /by category/i }));

    expect(screen.getByText("Food & Dining · Alice")).toBeInTheDocument();
  });

  it("settlement rows have dashed Txns and share cells", async () => {
    const data = makeData({
      recorded_settlements: [
        makeSettlement({
          amount: 100,
          from_person_id: ALICE_ID,
          to_person_id: BOB_ID,
          method: "venmo",
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );

    await expandLedger();

    const settlementRow = screen
      .getByText(/Alice → Bob via venmo/)
      .closest("tr") as HTMLElement;
    expect(settlementRow.textContent).toContain("$100.00");
    // 3 dashes: Txns, Alice's share, Bob's share
    const dashes = settlementRow.querySelectorAll("span");
    expect(dashes.length).toBeGreaterThanOrEqual(3);
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
      recorded_settlements: [
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

    // With no linked transactions the settlement row falls back to its own
    // year/month (waivers, manual records) — not the settled_at recording
    // moment, which here is April.
    const settlementLink = screen.getByRole("link", {
      name: /Alice → Bob via venmo/,
    });
    expect(settlementLink.getAttribute("href")).toContain("year=2026");
    expect(settlementLink.getAttribute("href")).toContain("month=3");
    expect(settlementLink.getAttribute("href")).toContain("settlement=1");
  });

  it("settlement rows link via the earliest linked transaction's date, not settled_at", async () => {
    const data = makeData({
      recorded_settlements: [
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

  it("by-category rows link with their own category filters, including Uncategorized", async () => {
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
          categories: ["Dining Out", "Groceries"],
        }),
        makeGroupSplit({
          payer_person_id: ALICE_ID,
          group_id: null,
          group_name: "Uncategorized",
          fronted: 142,
          their_share: 71,
          partner_share: 71,
          transaction_count: 3,
          categories: ["Weird Import Name"],
        }),
      ],
    });

    renderWithProviders(
      <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
    );

    await user.click(screen.getByRole("button", { name: /show ledger/i }));
    await user.click(screen.getByRole("radio", { name: /by category/i }));

    const foodLink = screen.getByRole("link", {
      name: "Food & Dining · Alice",
    });
    expect(foodLink.getAttribute("href")).toContain("cat=Dining+Out");
    expect(foodLink.getAttribute("href")).toContain("cat=Groceries");

    // Uncategorized rows must not produce an unfiltered URL.
    const uncatLink = screen.getByRole("link", {
      name: "Uncategorized · Alice",
    });
    expect(uncatLink.getAttribute("href")).toContain("cat=Weird+Import+Name");
  });

  it("shows empty-state row when there are no split bills", async () => {
    const data = makeData({
      recorded_settlements: [
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
            fronted: 2632.09,
            their_share: 1346.39,
            partner_share: 1285.7,
            transaction_count: 33,
          }),
          makePayerSplit({
            payer_person_id: BOB_ID,
            fronted: 6386.72,
            their_share: 3193.42,
            partner_share: 3193.3,
            transaction_count: 33,
          }),
        ],
        recorded_settlements: [
          makeSettlement({
            amount: 1981,
            from_person_id: ALICE_ID,
            to_person_id: BOB_ID,
            method: "Venmo",
            // Noon UTC so the rendered short-date is stable across local TZs.
            settled_at: "2026-04-26T12:00:00Z",
          }),
        ],
      });

      renderWithProviders(
        <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
      );

      // Net = +1285.70 − 3193.30 + 1981.00 = +73.40 → Bob owes Alice
      expect(
        screen.getByText(
          /Alice fronted \$2,632\.09 across 33 bills; Bob fronted \$6,386\.72 across 33 bills\. After splitting and one Venmo transfer on Apr 26, Bob owes Alice \$73\.40\./,
        ),
      ).toBeInTheDocument();
    });

    it("says 'the balance is settled' when net is zero", () => {
      const data = makeData({
        payer_splits: [
          makePayerSplit({ payer_person_id: ALICE_ID }),
          makePayerSplit({
            payer_person_id: BOB_ID,
            fronted: 100,
            their_share: 50,
            partner_share: 50,
            transaction_count: 1,
          }),
        ],
        recorded_settlements: [
          makeSettlement({
            amount: 50,
            from_person_id: ALICE_ID,
            to_person_id: BOB_ID,
            method: "Venmo",
            settled_at: "2026-04-22T00:00:00Z",
          }),
        ],
      });

      renderWithProviders(
        <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
      );

      expect(screen.getByText(/the balance is settled\.$/)).toBeInTheDocument();
    });

    it("treats float dust as settled — narrative and Total row agree", async () => {
      // Net = 0.1 − 0.3 + 0.2 = 2.7755575615628914e-17 in JS floats.
      const data = makeData({
        payer_splits: [
          makePayerSplit({
            payer_person_id: ALICE_ID,
            fronted: 0.2,
            their_share: 0.1,
            partner_share: 0.1,
            transaction_count: 1,
          }),
          makePayerSplit({
            payer_person_id: BOB_ID,
            fronted: 0.6,
            their_share: 0.3,
            partner_share: 0.3,
            transaction_count: 1,
          }),
        ],
        recorded_settlements: [
          makeSettlement({
            amount: 0.2,
            from_person_id: ALICE_ID,
            to_person_id: BOB_ID,
            method: "Venmo",
          }),
        ],
      });

      renderWithProviders(
        <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
      );

      expect(screen.getByText(/the balance is settled\.$/)).toBeInTheDocument();

      await expandLedger();
      const totalRow = screen.getByText("Total").closest("tr") as HTMLElement;
      expect(totalRow.textContent).toContain("$0.00");
      expect(totalRow.textContent).not.toContain("−$0.00");
      expect(totalRow.textContent).not.toContain("+$0.00");
    });

    it("uses singular 'bill' when count is one", () => {
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

      expect(
        screen.getByText(/Alice fronted \$100\.00 across 1 bill\./),
      ).toBeInTheDocument();
    });

    it("describes a waiver as 'a waiver'", () => {
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
        recorded_settlements: [
          makeSettlement({
            amount: 50,
            from_person_id: BOB_ID,
            to_person_id: ALICE_ID,
            is_waived: true,
          }),
        ],
      });

      renderWithProviders(
        <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
      );

      expect(
        screen.getByText(
          /After splitting and a waiver, the balance is settled\.$/,
        ),
      ).toBeInTheDocument();
    });

    it("counts multiple settlements", () => {
      const data = makeData({
        payer_splits: [
          makePayerSplit({
            payer_person_id: ALICE_ID,
            fronted: 200,
            their_share: 100,
            partner_share: 100,
            transaction_count: 2,
          }),
          makePayerSplit({ payer_person_id: BOB_ID }),
        ],
        recorded_settlements: [
          makeSettlement({
            id: "s1",
            amount: 30,
            from_person_id: BOB_ID,
            to_person_id: ALICE_ID,
            method: "Venmo",
          }),
          makeSettlement({
            id: "s2",
            amount: 70,
            from_person_id: BOB_ID,
            to_person_id: ALICE_ID,
            method: "Cash",
          }),
        ],
      });

      renderWithProviders(
        <SettleUpAuditTable data={data} personNames={PERSON_NAMES} />,
      );

      expect(
        screen.getByText(
          /After splitting and 2 settlements, the balance is settled\.$/,
        ),
      ).toBeInTheDocument();
    });
  });
});
