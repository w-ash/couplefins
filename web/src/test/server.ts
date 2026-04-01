import { setupServer } from "msw/node";
import { getBudgetsMock } from "@/api/generated/budgets/budgets.msw";
import { getCategoryGroupsMock } from "@/api/generated/category-groups/category-groups.msw";
import { getDashboardMock } from "@/api/generated/dashboard/dashboard.msw";
import { getHealthCheckMockHandler } from "@/api/generated/health/health.msw";
import { getInsightsMock } from "@/api/generated/insights/insights.msw";
import { getPersonsMock } from "@/api/generated/persons/persons.msw";
import { getReconciliationMock } from "@/api/generated/reconciliation/reconciliation.msw";
import { getSettlementsMock } from "@/api/generated/settlements/settlements.msw";
import { getTransactionsMock } from "@/api/generated/transactions/transactions.msw";
import { getUploadsMock } from "@/api/generated/uploads/uploads.msw";

export const server = setupServer(
  getHealthCheckMockHandler({
    status: "ok",
    version: "1.1.0",
    schema_version: "0004",
    schema_current: "0004",
    schema_ok: true,
    database_host: "localhost",
    database_mode: "Local PostgreSQL",
  }),
  ...getPersonsMock(),
  ...getUploadsMock(),
  ...getCategoryGroupsMock(),
  ...getReconciliationMock(),
  ...getDashboardMock(),
  ...getBudgetsMock(),
  ...getTransactionsMock(),
  ...getSettlementsMock(),
  ...getInsightsMock(),
);
