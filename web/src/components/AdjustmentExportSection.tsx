import {
  ArrowDownLeft,
  ArrowUpRight,
  Check,
  ChevronDown,
  Download,
  Loader2,
} from "lucide-react";
import { useCallback, useState } from "react";
import type { AdjustmentResponse } from "@/api/generated/model";
import { usePreviewAdjustments } from "@/api/generated/persons/persons";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError } from "@/components/InlineError";
import { PersonBadge } from "@/components/PersonBadge";
import { useTemporary } from "@/hooks/useTemporary";
import { downloadAdjustmentCsv } from "@/lib/adjustments";
import { formatCurrency, formatDate, plural } from "@/lib/format";
import { usePersonMaps } from "@/lib/persons";
import type { Person } from "@/types/person";

function AdjustmentRow({ adjustment }: { adjustment: AdjustmentResponse }) {
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
  const {
    data: response,
    isLoading,
    error,
  } = usePreviewAdjustments(personId, year, month, {
    query: { enabled: expanded },
  });
  const data = response?.status === 200 ? response.data : undefined;

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

          {error && (
            <InlineError>
              {error instanceof Error ? error.message : "Failed to load"}
            </InlineError>
          )}

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
  accentColor,
  year,
  month,
}: {
  person: Person;
  accentColor: string;
  year: number;
  month: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [successMessage, setSuccessMessage] = useTemporary<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleDownload = useCallback(async () => {
    setIsDownloading(true);
    setErrorMessage(null);
    try {
      const { rowCount } = await downloadAdjustmentCsv(person.id, year, month);
      setSuccessMessage(`Downloaded ${plural("row", rowCount)}`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Download failed");
    } finally {
      setIsDownloading(false);
    }
  }, [person.id, year, month, setSuccessMessage]);

  const hasAccount = person.adjustment_account.trim() !== "";

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-3">
        <PersonBadge name={person.name} accentColor={accentColor} />

        <div className="flex items-center gap-2">
          {successMessage ? (
            <span className="inline-flex items-center gap-1 text-sm text-positive">
              <Check className="size-4" />
              {successMessage}
            </span>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              disabled={!hasAccount || isDownloading}
              loading={isDownloading}
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

      {errorMessage && <InlineError>{errorMessage}</InlineError>}

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
  const { getPersonColor } = usePersonMaps(persons);

  return (
    <Card>
      <h2 className="mb-4 font-medium text-lg text-foreground">
        Export Adjustments
      </h2>
      <div className="space-y-5">
        {persons.map((person) => (
          <PersonExportCard
            key={person.id}
            person={person}
            accentColor={getPersonColor(person.id)}
            year={year}
            month={month}
          />
        ))}
      </div>
    </Card>
  );
}
