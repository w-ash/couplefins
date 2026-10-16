import type {
  ActivityKind,
  ContributionKind,
  DashboardPersonResponse,
  LoanKind,
  ObligationKind,
  OwnerAmountResponse,
} from "@/api/generated/model";

/** One owner of the house, as the House response names them. */
export type Owner = DashboardPersonResponse;

export const CONTRIBUTION_KIND_LABELS: Record<ContributionKind, string> = {
  closing: "Closing",
  "loan-interest": "Loan interest",
  "loan-principal": "Loan principal",
  "property-tax": "Property tax",
  insurance: "Insurance",
  repair: "Repairs",
  "agreed-work": "Agreed work",
};

export const LOAN_KIND_LABELS: Record<LoanKind, string> = {
  interest_only: "Interest only",
  amortizing: "Amortizing",
};

export const OBLIGATION_KIND_LABELS: Record<ObligationKind, string> = {
  loan_payment: "Loan payment",
  property_tax: "Property tax",
  insurance: "Insurance",
  other: "Other",
};

export const ACTIVITY_KIND_LABELS: Record<ActivityKind, string> = {
  deposit: "Deposit",
  payment: "Payment",
  refund: "Refund",
  transfer: "Transfer",
};

/** Looks up one owner's entry in a per-owner list served in persons order. */
export function forOwner<T extends { person_id: string }>(
  list: T[],
  personId: string,
): T | undefined {
  return list.find((entry) => entry.person_id === personId);
}

/** One owner's amount in a per-owner list, 0 when the list has no entry. */
export function ownerAmount(
  list: OwnerAmountResponse[],
  personId: string,
): number {
  return forOwner(list, personId)?.amount ?? 0;
}
