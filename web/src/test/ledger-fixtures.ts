import type {
  LedgerMonthResponse,
  LedgerSettlementResponse,
} from "@/api/generated/model";

// Shared ledger fixture skeletons for the Settle Up suites. Each suite wraps
// these with its own scenario defaults (people, viewed month, amounts).

export function makeLedgerMonth(
  overrides: Partial<LedgerMonthResponse> &
    Pick<LedgerMonthResponse, "year" | "month">,
): LedgerMonthResponse {
  return {
    charged: null,
    paid: null,
    balance: null,
    status: "settled",
    runs_against_year: false,
    ...overrides,
  };
}

export function makeLedgerSettlement(
  overrides: Partial<LedgerSettlementResponse> &
    Pick<LedgerSettlementResponse, "id" | "from_person_id" | "to_person_id">,
): LedgerSettlementResponse {
  return {
    amount: 0,
    method: null,
    is_waived: false,
    notes: "",
    settled_at: "",
    created_at: "",
    linked_transaction_ids: [],
    linked_transactions: [],
    portions: [],
    ...overrides,
  };
}
