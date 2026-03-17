import { setupServer } from "msw/node";
import { getBudgetsMock } from "@/api/generated/budgets/budgets.msw";
import { getCategoryGroupsMock } from "@/api/generated/category-groups/category-groups.msw";
import { getDashboardMock } from "@/api/generated/dashboard/dashboard.msw";
import { getHealthMock } from "@/api/generated/health/health.msw";
import { getPersonsMock } from "@/api/generated/persons/persons.msw";
import { getReconciliationMock } from "@/api/generated/reconciliation/reconciliation.msw";
import { getSettlementsMock } from "@/api/generated/settlements/settlements.msw";
import { getTransactionsMock } from "@/api/generated/transactions/transactions.msw";
import { getUploadsMock } from "@/api/generated/uploads/uploads.msw";

export const server = setupServer(
  ...getHealthMock(),
  ...getPersonsMock(),
  ...getUploadsMock(),
  ...getCategoryGroupsMock(),
  ...getReconciliationMock(),
  ...getDashboardMock(),
  ...getBudgetsMock(),
  ...getTransactionsMock(),
  ...getSettlementsMock(),
);
