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
import { forOwner, type Owner } from "@/lib/house";
import { amountCellClass, cellClass, tableHeaderRowClass } from "@/lib/layout";

/** The cell of a bank figure not entered yet. */
const NO_BANK_BALANCE = (
  <span title="Enter the bank balance in House settings">—</span>
);

const DEPOSIT_COLUMNS = ["Own", "Gift", "Share of payments", "Unspent"];

export function SetAsideSection({
  setAside,
  owners,
  example = false,
}: {
  example?: boolean;
  setAside: SetAsideSectionResponse;
  owners: Owner[];
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
                  <td
                    className={cn(
                      cellClass,
                      b.is_unassigned && "text-muted-foreground",
                    )}
                  >
                    {b.name}
                    {b.is_unassigned && (
                      <span className="ml-2 text-xs">no pot tag</span>
                    )}
                  </td>
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
                      NO_BANK_BALANCE
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
                      : NO_BANK_BALANCE}
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
      {setAside.owners.length > 0 && (
        <>
          <h3
            id="house-deposits"
            className="mt-6 mb-2 text-sm font-medium text-foreground"
          >
            Deposits
          </h3>
          <div className="overflow-x-auto">
            <table aria-labelledby="house-deposits" className="w-full text-sm">
              <thead>
                <tr className={tableHeaderRowClass}>
                  <th scope="col" className={cn(cellClass, "font-medium")}>
                    Owner
                  </th>
                  {DEPOSIT_COLUMNS.map((label) => (
                    <th
                      key={label}
                      scope="col"
                      className={cn(amountCellClass, "font-medium")}
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {owners.map((o) => {
                  const d = forOwner(setAside.owners, o.id);
                  return (
                    d && (
                      <tr key={o.id} className="border-b border-border/60">
                        <td className={cellClass}>{o.name}</td>
                        <td className={amountCellClass}>
                          {formatCurrency(d.own_deposits)}
                        </td>
                        <td className={amountCellClass}>
                          {formatCurrency(d.gift_deposits)}
                        </td>
                        <td className={amountCellClass}>
                          {formatCurrency(d.share_of_payments)}
                        </td>
                        <td className={cn(amountCellClass, "font-medium")}>
                          {formatCurrency(d.unspent)}
                        </td>
                      </tr>
                    )
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
