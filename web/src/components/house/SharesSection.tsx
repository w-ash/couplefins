import type { SharesSectionResponse } from "@/api/generated/model";
import { Card } from "@/components/Card";
import { PersonBadge } from "@/components/PersonBadge";
import { ProgressBar } from "@/components/ProgressBar";
import { SectionHeader } from "@/components/SectionHeader";
import { formatCurrency, formatPercent } from "@/lib/format";
import { forOwner, type Owner } from "@/lib/house";
import { nestedCardClass } from "@/lib/layout";
import { getPersonBarColor } from "@/types/person";
import { ShareHistoryChart } from "./ShareHistoryChart";

export function SharesSection({
  shares,
  owners,
  getPersonColor,
  getPersonIndex,
}: {
  shares: SharesSectionResponse;
  owners: Owner[];
  getPersonColor: (id: string) => string;
  getPersonIndex: (id: string) => number;
}) {
  return (
    <Card as="section" aria-labelledby="house-shares">
      <SectionHeader
        id="house-shares"
        title="Shares"
        description="Each owner's share of the house, now and over time."
      />
      <div className="grid gap-3 sm:grid-cols-2">
        {owners.map((o) => {
          const share = forOwner(shares.now, o.id);
          return (
            <div key={o.id} className={nestedCardClass}>
              <div className="flex items-center justify-between gap-2">
                <PersonBadge name={o.name} accentColor={getPersonColor(o.id)} />
                <span className="text-lg font-semibold tabular-nums">
                  {share ? formatPercent(share.percent) : "—"}
                </span>
              </div>
              <p className="mt-2 text-sm tabular-nums">
                {formatCurrency(share?.capital ?? 0)}
              </p>
              <div className="mt-2">
                <ProgressBar
                  pct={share?.percent ?? 0}
                  barColor={getPersonBarColor(getPersonIndex(o.id))}
                />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                of {formatCurrency(shares.total_capital)} put in
              </p>
            </div>
          );
        })}
      </div>
      <div className="mt-4">
        <ShareHistoryChart
          history={shares.history}
          owners={owners}
          getPersonIndex={getPersonIndex}
        />
      </div>
    </Card>
  );
}
