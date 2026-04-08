import { Database, Settings } from "lucide-react";
import { useHealthCheck } from "@/api/generated/health/health";
import { Card } from "@/components/Card";
import { CategoryMappingEditor } from "@/components/CategoryMappingEditor";
import { PageHeader } from "@/components/PageHeader";
import { PersonAccountSettings } from "@/components/PersonAccountSettings";
import { SectionHeader } from "@/components/SectionHeader";
import { SettlementMerchantsEditor } from "@/components/SettlementMerchantsEditor";
import { PAGE_PADDING } from "@/lib/layout";

export function SettingsPage() {
  const { data: healthResponse } = useHealthCheck();
  const health =
    healthResponse?.status === 200 ? healthResponse.data : undefined;

  return (
    <div className={`mx-auto max-w-3xl ${PAGE_PADDING}`}>
      <PageHeader icon={<Settings className="size-6" />} title="Settings" />

      <div className="space-y-6">
        {/* Category Mappings */}
        <Card as="section" aria-labelledby="settings-category-mappings">
          <SectionHeader
            id="settings-category-mappings"
            title="Category Groups"
            description="Map Monarch categories to budget groups"
          />
          <CategoryMappingEditor />
        </Card>

        {/* People */}
        <Card as="section" aria-labelledby="settings-people">
          <SectionHeader
            id="settings-people"
            title="People"
            description="Names and Monarch adjustment account names for CSV export"
          />
          <PersonAccountSettings />
        </Card>

        {/* Settlement Merchants */}
        <Card as="section" aria-labelledby="settings-settlement-merchants">
          <SectionHeader
            id="settings-settlement-merchants"
            title="Settlement Merchants"
            description="Transactions from these merchants can be auto-detected and linked to payments, so they don't inflate your spending totals"
          />
          <SettlementMerchantsEditor />
        </Card>

        {/* System */}
        {health && (
          <Card as="section" aria-labelledby="settings-system">
            <h2
              id="settings-system"
              className="mb-3 font-medium text-lg text-foreground"
            >
              System
            </h2>
            <div className="flex items-center gap-3 rounded-lg border border-border-muted bg-muted/30 px-4 py-3">
              <Database className="size-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 text-sm">
                <span className="font-medium text-foreground">
                  {health.database_mode}
                </span>
                <span className="ml-2 font-mono text-xs text-muted-foreground">
                  {health.database_host}
                </span>
              </div>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
