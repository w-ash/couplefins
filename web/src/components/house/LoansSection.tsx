import type { LoanResponse } from "@/api/generated/model";
import { Card } from "@/components/Card";
import { PersonBadge } from "@/components/PersonBadge";
import { SectionHeader } from "@/components/SectionHeader";
import { StatsGrid } from "@/components/StatsGrid";
import { formatCurrency, formatDate, formatPercent } from "@/lib/format";
import { LOAN_KIND_LABELS, type Owner, ownerAmount } from "@/lib/house";
import { nestedCardClass } from "@/lib/layout";

export function LoansSection({
  loans,
  owners,
  getPersonColor,
}: {
  loans: LoanResponse[];
  owners: Owner[];
  getPersonColor: (id: string) => string;
}) {
  return (
    <Card as="section" aria-labelledby="house-loans">
      <SectionHeader
        id="house-loans"
        title="Loans"
        description="What is owed on the house and who pays what."
      />
      {loans.length === 0 ? (
        <p className="text-sm text-muted-foreground">No loans recorded yet.</p>
      ) : (
        <div className="space-y-4">
          {loans.map((loan) => (
            <div key={loan.id} className={nestedCardClass}>
              <div className="mb-3 flex items-baseline gap-2">
                <h3 className="font-medium text-foreground">{loan.name}</h3>
                <span className="text-xs text-muted-foreground">
                  {LOAN_KIND_LABELS[loan.kind]}
                </span>
              </div>
              <StatsGrid
                stats={[
                  { label: "Balance", value: formatCurrency(loan.balance) },
                  { label: "Rate", value: formatPercent(loan.rate_percent, 2) },
                  { label: "Payment", value: formatCurrency(loan.payment) },
                  { label: "Next due", value: formatDate(loan.next_due) },
                ]}
              />
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
                <span className="text-xs font-medium text-muted-foreground">
                  Each owner's part
                </span>
                {owners.map((o) => (
                  <span key={o.id} className="flex items-center gap-2">
                    <PersonBadge
                      name={o.name}
                      accentColor={getPersonColor(o.id)}
                      size="xs"
                    />
                    <span className="text-sm tabular-nums">
                      {formatCurrency(ownerAmount(loan.owner_parts, o.id))}
                    </span>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
