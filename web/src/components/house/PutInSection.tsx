import type { PutInSectionResponse } from "@/api/generated/model";
import { Card } from "@/components/Card";
import { SectionHeader } from "@/components/SectionHeader";
import { StatsGrid } from "@/components/StatsGrid";
import { cn } from "@/lib/cn";
import { formatCurrency } from "@/lib/format";
import { CONTRIBUTION_KIND_LABELS, type Owner, ownerAmount } from "@/lib/house";
import { amountCellClass, cellClass, tableHeaderRowClass } from "@/lib/layout";

export function PutInSection({
  putIn,
  owners,
  example = false,
}: {
  example?: boolean;
  putIn: PutInSectionResponse;
  owners: Owner[];
}) {
  return (
    <Card as="section" aria-labelledby="house-put-in">
      <SectionHeader
        example={example}
        id="house-put-in"
        title="Put in"
        description="What each owner has put into the house to date."
      />
      <StatsGrid
        stats={[
          ...owners.map((o) => ({
            label: o.name,
            value: formatCurrency(ownerAmount(putIn.totals, o.id)),
          })),
          { label: "Together", value: formatCurrency(putIn.total) },
        ]}
      />
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className={tableHeaderRowClass}>
              <th scope="col" className={cn(cellClass, "font-medium")}>
                Kind
              </th>
              {owners.map((o) => (
                <th
                  key={o.id}
                  scope="col"
                  className={cn(amountCellClass, "font-medium")}
                >
                  {o.name}
                </th>
              ))}
              <th scope="col" className={cn(amountCellClass, "font-medium")}>
                Total
              </th>
            </tr>
          </thead>
          <tbody>
            {putIn.kinds.map((row) => (
              <tr key={row.kind} className="border-b border-border/60">
                <td className={cellClass}>
                  {CONTRIBUTION_KIND_LABELS[row.kind]}
                </td>
                {owners.map((o) => (
                  <td key={o.id} className={amountCellClass}>
                    {formatCurrency(ownerAmount(row.amounts, o.id))}
                  </td>
                ))}
                <td className={cn(amountCellClass, "font-medium")}>
                  {formatCurrency(row.total)}
                </td>
              </tr>
            ))}
            <tr className="text-muted-foreground">
              <td className={cellClass}>Deposits not yet spent</td>
              {owners.map((o) => (
                <td key={o.id} className={amountCellClass}>
                  {formatCurrency(ownerAmount(putIn.unspent_deposits, o.id))}
                </td>
              ))}
              <td className={cellClass} />
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  );
}
