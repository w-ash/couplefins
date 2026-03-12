import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Check,
  ChevronDown,
  Download,
  Loader2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/Button";
import {
  type AdjustmentPreview,
  downloadAdjustmentCsv,
  fetchAdjustmentPreview,
} from "@/lib/adjustments";
import { formatCurrency, formatDate } from "@/lib/format";
import { getPersonAccentColor, type Person } from "@/types/person";

function AdjustmentRow({ adjustment }: { adjustment: AdjustmentPreview }) {
  const isCredit = adjustment.amount >= 0;

  return (
    <tr className="border-b border-border-muted">
      <td className="py-2 pr-4 text-muted-foreground tabular-nums">
        {formatDate(adjustment.date)}
      </td>
      <td className="py-2 pr-4 text-foreground">{adjustment.merchant}</td>
      <td className="py-2 pr-4 text-muted-foreground">{adjustment.category}</td>
      <td
        className={`py-2 pr-4 text-sm ${isCredit ? "text-positive" : "text-negative"}`}
      >
        <span className="inline-flex items-center gap-1">
          {isCredit ? (
            <ArrowUpRight className="size-3.5" />
          ) : (
            <ArrowDownLeft className="size-3.5" />
          )}
          {isCredit ? "Credit" : "Debit"}
        </span>
      </td>
      <td
        className={`py-2 text-right tabular-nums ${
          isCredit ? "text-positive" : "text-negative"
        }`}
      >
        {formatCurrency(adjustment.amount)}
      </td>
    </tr>
  );
}

function PreviewTable({
  personId,
  year,
  month,
  expanded,
}: {
  personId: string;
  year: number;
  month: number;
  expanded: boolean;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["adjustments", personId, year, month],
    queryFn: () => fetchAdjustmentPreview(personId, year, month),
    enabled: expanded,
  });

  return (
    <div
      className="grid transition-[grid-template-rows] duration-200"
      style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
    >
      <div className="overflow-hidden">
        <div className="pt-4">
          {isLoading && (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="size-4 animate-spin text-muted-foreground" />
            </div>
          )}

          {error && <p className="text-sm text-negative">{error.message}</p>}

          {data && data.adjustments.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No adjustments for this month.
            </p>
          )}

          {data && data.adjustments.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="pb-2 pr-4 font-medium">Date</th>
                    <th className="pb-2 pr-4 font-medium">Merchant</th>
                    <th className="pb-2 pr-4 font-medium">Category</th>
                    <th className="pb-2 pr-4 font-medium">Type</th>
                    <th className="pb-2 text-right font-medium">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {data.adjustments.map((adj) => (
                    <AdjustmentRow key={adj.dedup_id} adjustment={adj} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PersonExportCard({
  person,
  personIndex,
  year,
  month,
}: {
  person: Person;
  personIndex: number;
  year: number;
  month: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [download, setDownload] = useState<
    | { status: "idle" }
    | { status: "loading" }
    | { status: "success"; message: string }
    | { status: "error"; message: string }
  >({ status: "idle" });

  useEffect(() => {
    if (download.status !== "success") return;
    const id = setTimeout(() => setDownload({ status: "idle" }), 2000);
    return () => clearTimeout(id);
  }, [download]);

  const handleDownload = useCallback(async () => {
    setDownload({ status: "loading" });
    try {
      const { rowCount } = await downloadAdjustmentCsv(person.id, year, month);
      setDownload({
        status: "success",
        message: `Downloaded ${rowCount} row${rowCount !== 1 ? "s" : ""}`,
      });
    } catch (err) {
      setDownload({
        status: "error",
        message: err instanceof Error ? err.message : "Download failed",
      });
    }
  }, [person.id, year, month]);

  const hasAccount = person.adjustment_account.trim() !== "";
  const accentColor = getPersonAccentColor(personIndex);

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-3">
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-sm font-medium ${accentColor}`}
        >
          {person.name}
        </span>

        <div className="flex items-center gap-2">
          {download.status === "success" ? (
            <span className="inline-flex items-center gap-1 text-sm text-positive">
              <Check className="size-4" />
              {download.message}
            </span>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              disabled={!hasAccount || download.status === "loading"}
              loading={download.status === "loading"}
              loadingText="Downloading"
              icon={<Download className="size-4" />}
              onClick={handleDownload}
            >
              Download Adjustments
            </Button>
          )}

          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            disabled={!hasAccount}
            className="flex items-center gap-1 text-sm text-muted-foreground transition-colors duration-150 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ChevronDown
              className={`size-4 transition-transform duration-200 ${
                expanded ? "" : "-rotate-90"
              }`}
            />
            Preview
          </button>
        </div>
      </div>

      {!hasAccount && (
        <p className="text-sm text-muted-foreground">
          Set adjustment account in Settings to enable export.
        </p>
      )}

      {download.status === "error" && (
        <p className="text-sm text-negative">{download.message}</p>
      )}

      {hasAccount && (
        <PreviewTable
          personId={person.id}
          year={year}
          month={month}
          expanded={expanded}
        />
      )}
    </div>
  );
}

export function AdjustmentExportSection({
  persons,
  year,
  month,
}: {
  persons: Person[];
  year: number;
  month: number;
}) {
  const personIndexMap = useMemo(
    () => new Map(persons.map((p, i) => [p.id, i])),
    [persons],
  );

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
      <h2 className="mb-4 font-medium text-lg text-foreground">
        Export Adjustments
      </h2>
      <div className="space-y-5">
        {persons.map((person) => (
          <PersonExportCard
            key={person.id}
            person={person}
            personIndex={personIndexMap.get(person.id) ?? 0}
            year={year}
            month={month}
          />
        ))}
      </div>
    </div>
  );
}
