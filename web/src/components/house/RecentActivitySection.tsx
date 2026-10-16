import type { ActivityRowResponse } from "@/api/generated/model";
import { Card } from "@/components/Card";
import { PersonBadge } from "@/components/PersonBadge";
import { SectionHeader } from "@/components/SectionHeader";
import { cn } from "@/lib/cn";
import {
  amountColorClass,
  formatCurrency,
  formatDate,
  formatSignedCurrency,
} from "@/lib/format";
import { type Owner, ownerAmount } from "@/lib/house";
import { amountCellClass, cellClass, tableHeaderRowClass } from "@/lib/layout";
import { ActivityKindPill } from "./ActivityKindPill";

export function RecentActivitySection({
  activity,
  owners,
  getPersonName,
  getPersonColor,
}: {
  activity: ActivityRowResponse[];
  owners: Owner[];
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
}) {
  const sharesText = (row: ActivityRowResponse) =>
    owners
      .map((o) => `${o.name} ${formatCurrency(ownerAmount(row.shares, o.id))}`)
      .join(" · ");

  return (
    <Card as="section" aria-labelledby="house-activity">
      <SectionHeader
        id="house-activity"
        title="Recent activity"
        description="The latest movement on the joint accounts."
      />
      {activity.length === 0 ? (
        <p className="text-sm text-muted-foreground">No activity yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={tableHeaderRowClass}>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  Date
                </th>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  Who
                </th>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  Kind
                </th>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  Budget line
                </th>
                <th scope="col" className={cn(amountCellClass, "font-medium")}>
                  Amount
                </th>
              </tr>
            </thead>
            <tbody>
              {activity.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-border/60 align-top"
                >
                  <td className={cn(cellClass, "whitespace-nowrap")}>
                    {formatDate(row.date)}
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {row.account_name}
                    </p>
                  </td>
                  <td className={cellClass}>
                    {row.person_id ? (
                      <PersonBadge
                        name={getPersonName(row.person_id)}
                        accentColor={getPersonColor(row.person_id)}
                        size="xs"
                      />
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className={cellClass}>
                    <ActivityKindPill kind={row.kind} />
                  </td>
                  <td className={cellClass}>{row.budget_line ?? "—"}</td>
                  <td
                    className={cn(
                      amountCellClass,
                      amountColorClass(row.amount),
                    )}
                  >
                    {formatSignedCurrency(row.amount)}
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {sharesText(row)}
                    </p>
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
