import { AlertTriangle } from "lucide-react";
import type { ObligationResponse } from "@/api/generated/model";
import { Card } from "@/components/Card";
import { Pill } from "@/components/Pill";
import { SectionHeader } from "@/components/SectionHeader";
import { cn } from "@/lib/cn";
import { formatCurrency, formatDate } from "@/lib/format";
import { OBLIGATION_KIND_LABELS } from "@/lib/house";
import { amountCellClass, cellClass, tableHeaderRowClass } from "@/lib/layout";

export function UpcomingSection({
  upcoming,
}: {
  upcoming: ObligationResponse[];
}) {
  return (
    <Card as="section" aria-labelledby="house-upcoming">
      <SectionHeader
        id="house-upcoming"
        title="Upcoming"
        description="Obligations coming due and the bucket that pays each."
      />
      {upcoming.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing coming due.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={tableHeaderRowClass}>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  What
                </th>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  Due
                </th>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  Late after
                </th>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  Paid from
                </th>
                <th scope="col" className={cn(amountCellClass, "font-medium")}>
                  Amount
                </th>
              </tr>
            </thead>
            <tbody>
              {upcoming.map((o) => (
                <tr key={o.id} className="border-b border-border/60 align-top">
                  <td className={cellClass}>
                    <span className="font-medium">{o.name}</span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      {OBLIGATION_KIND_LABELS[o.kind]}
                    </span>
                    {o.is_estimate && <Pill className="ml-2">estimate</Pill>}
                  </td>
                  <td className={cn(cellClass, "whitespace-nowrap")}>
                    {formatDate(o.due)}
                  </td>
                  <td className={cn(cellClass, "whitespace-nowrap")}>
                    {o.late_after ? formatDate(o.late_after) : "—"}
                  </td>
                  <td className={cellClass}>{o.pays_from ?? "—"}</td>
                  <td className={amountCellClass}>
                    {formatCurrency(o.amount)}
                    {o.shortfall != null && (
                      <p className="mt-0.5 flex items-center justify-end gap-1 text-xs font-medium text-warning-muted-foreground">
                        <AlertTriangle className="size-3.5" aria-hidden />
                        Short by {formatCurrency(o.shortfall)}
                      </p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
