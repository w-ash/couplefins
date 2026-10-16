import type { SetAsideSectionResponse } from "@/api/generated/model";
import { Card } from "@/components/Card";
import { SectionHeader } from "@/components/SectionHeader";
import { cn } from "@/lib/cn";
import {
  amountColorClass,
  formatCurrency,
  formatDate,
  formatSignedCurrency,
} from "@/lib/format";
import { amountCellClass, cellClass, tableHeaderRowClass } from "@/lib/layout";

export function SetAsideSection({
  setAside,
  example = false,
}: {
  example?: boolean;
  setAside: SetAsideSectionResponse;
}) {
  return (
    <Card as="section" aria-labelledby="house-set-aside">
      <SectionHeader
        example={example}
        id="house-set-aside"
        title="Set aside"
        description="Each bucket beside the balance last entered from the bank."
      />
      {setAside.buckets.length === 0 ? (
        <p className="text-sm text-muted-foreground">No money set aside yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={tableHeaderRowClass}>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  Bucket
                </th>
                <th scope="col" className={cn(amountCellClass, "font-medium")}>
                  Set aside
                </th>
                <th scope="col" className={cn(amountCellClass, "font-medium")}>
                  Bank balance
                </th>
                <th scope="col" className={cn(amountCellClass, "font-medium")}>
                  Difference
                </th>
              </tr>
            </thead>
            <tbody>
              {setAside.buckets.map((b) => (
                <tr
                  key={b.name}
                  className="border-b border-border/60 align-top"
                >
                  <td className={cellClass}>{b.name}</td>
                  <td className={amountCellClass}>
                    {formatCurrency(b.balance)}
                  </td>
                  <td className={amountCellClass}>
                    {b.bank_balance != null ? (
                      <>
                        {formatCurrency(b.bank_balance)}
                        {b.bank_balance_as_of && (
                          <p className="text-xs text-muted-foreground">
                            as of {formatDate(b.bank_balance_as_of)}
                          </p>
                        )}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td
                    className={cn(
                      amountCellClass,
                      b.difference != null && amountColorClass(b.difference),
                    )}
                  >
                    {b.difference != null
                      ? formatSignedCurrency(b.difference)
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="font-medium">
                <td className={cellClass}>Total</td>
                <td className={amountCellClass}>
                  {formatCurrency(setAside.total)}
                </td>
                <td className={cellClass} />
                <td className={cellClass} />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </Card>
  );
}
