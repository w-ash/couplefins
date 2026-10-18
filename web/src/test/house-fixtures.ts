import type { HouseResponse } from "@/api/generated/model";

export const ALICE_ID = "00000000-0000-0000-0000-000000000001";
export const BOB_ID = "00000000-0000-0000-0000-000000000002";

const owners = (a: number, b: number) => [
  { person_id: ALICE_ID, amount: a },
  { person_id: BOB_ID, amount: b },
];

const sharesNow = [
  { person_id: ALICE_ID, capital: 61200, percent: 60 },
  { person_id: BOB_ID, capital: 40800, percent: 40 },
];

/** An example-data House response for Alice and Bob; override any section. */
export function makeHouseResponse(
  overrides: Partial<HouseResponse> = {},
): HouseResponse {
  return {
    example_sections: [
      "put_in",
      "shares",
      "loans",
      "upcoming",
      "set_aside",
      "recent_activity",
    ],
    asset: {
      id: "asset-1",
      name: "Maple Street",
      repair_threshold: 500,
      qualifying_kinds: ["closing", "repair"],
      bank_balance: null,
      bank_balance_as_of: null,
      created_at: "2026-10-01T00:00:00Z",
    },
    as_of: "2026-10-15",
    persons: [
      { id: ALICE_ID, name: "Alice" },
      { id: BOB_ID, name: "Bob" },
    ],
    put_in: {
      kinds: [
        { kind: "closing", amounts: owners(60000, 40000), total: 100000 },
        { kind: "repair", amounts: owners(1200, 800), total: 2000 },
      ],
      totals: owners(61200, 40800),
      total: 102000,
      unspent_deposits: owners(500, 250),
    },
    shares: {
      now: sharesNow,
      total_capital: 102000,
      history: [
        {
          year: 2026,
          month: 8,
          owners: [
            { person_id: ALICE_ID, capital: 60000, percent: 60 },
            { person_id: BOB_ID, capital: 40000, percent: 40 },
          ],
        },
        { year: 2026, month: 9, owners: sharesNow },
      ],
    },
    loans: [
      {
        id: "loan-1",
        name: "Family loan",
        lender: "Example Bank",
        kind: "interest_only",
        principal: 250000,
        balance: 250000,
        rate_percent: 4.5,
        payment: 937.5,
        statement_balance: 250000,
        statement_balance_as_of: "2026-10-01",
        next_due: "2026-11-01",
        owner_parts: owners(562.5, 375),
      },
    ],
    past_loans: [
      {
        id: "loan-0",
        name: "Starter loan",
        lender: "Example Bank",
        kind: "amortizing",
        principal: 200000,
        balance: 0,
        rate_percent: 6.25,
        payment: 1500,
        statement_balance: 0,
        statement_balance_as_of: "2026-06-30",
        closed_on: "2026-06-30",
        replaced_by_loan_id: "loan-1",
      },
    ],
    upcoming: [
      {
        id: "ob-0",
        name: "Family loan payment",
        kind: "loan_payment",
        status: "late",
        amount: 937.5,
        is_estimate: false,
        due: "2026-10-01",
        late_after: "2026-10-10",
        pays_from: null,
        loan_id: "loan-1",
        paid_by_transaction_id: null,
        shortfall: null,
      },
      {
        id: "ob-1",
        name: "Property tax",
        kind: "property_tax",
        status: "due",
        amount: 3200,
        is_estimate: true,
        due: "2026-11-30",
        late_after: "2026-12-10",
        pays_from: "Tax reserve",
        loan_id: null,
        paid_by_transaction_id: null,
        shortfall: 450,
      },
      {
        id: "ob-2",
        name: "Insurance",
        kind: "insurance",
        status: "due",
        amount: 1400,
        is_estimate: false,
        due: "2027-01-15",
        late_after: null,
        pays_from: null,
        loan_id: null,
        paid_by_transaction_id: null,
        shortfall: null,
      },
    ],
    recent_paid: [
      {
        id: "ob-9",
        name: "Water bill",
        kind: "other",
        status: "paid",
        amount: 85,
        is_estimate: false,
        due: "2026-09-20",
        late_after: null,
        pays_from: null,
        loan_id: null,
        paid_by_transaction_id: "tx-9",
        shortfall: null,
      },
    ],
    set_aside: {
      buckets: [
        {
          name: "Tax reserve",
          balance: 2750,
          bank_balance: null,
          bank_balance_as_of: null,
          difference: null,
          is_unassigned: false,
        },
        {
          name: "Repairs fund",
          balance: 900,
          bank_balance: null,
          bank_balance_as_of: null,
          difference: null,
          is_unassigned: false,
        },
        {
          name: "Unassigned",
          balance: -60,
          bank_balance: null,
          bank_balance_as_of: null,
          difference: null,
          is_unassigned: true,
        },
      ],
      total: 3590,
      bank_balance: 3640,
      bank_balance_as_of: "2026-10-01",
      difference: 50,
      owners: [
        {
          person_id: ALICE_ID,
          own_deposits: 4000,
          gift_deposits: 0,
          share_of_payments: 1825,
          unspent: 2175,
        },
        {
          person_id: BOB_ID,
          own_deposits: 2200,
          gift_deposits: 1000,
          share_of_payments: 1785,
          unspent: 1415,
        },
      ],
    },
    recent_activity: [
      {
        id: "act-1",
        date: "2026-10-03",
        account_name: "Joint checking",
        person_id: ALICE_ID,
        kind: "deposit",
        budget_line: null,
        amount: 300,
        shares: owners(300, 0),
      },
      {
        id: "act-2",
        date: "2026-10-01",
        account_name: "Joint checking",
        person_id: null,
        kind: "payment",
        budget_line: null,
        amount: -937.5,
        shares: owners(562.5, 375),
      },
    ],
    ...overrides,
  };
}
