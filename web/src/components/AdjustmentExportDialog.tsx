import {
  ArrowDownLeft,
  ArrowUpRight,
  Check,
  Download,
  Loader2,
  X,
} from "lucide-react";
import { useCallback, useState } from "react";
import { Link } from "react-router";
import type { AdjustmentResponse } from "@/api/generated/model";
import {
  useGetPersons,
  usePreviewAdjustments,
} from "@/api/generated/persons/persons";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/InlineError";
import { useDialogSync } from "@/hooks/useDialogSync";
import { useTemporary } from "@/hooks/useTemporary";
import { downloadAdjustmentCsv } from "@/lib/adjustments";
import { formatCurrency, formatDate, MONTHS, plural } from "@/lib/format";
import { useIdentityStore } from "@/lib/identity";

function AdjustmentRow({ adj }: { adj: AdjustmentResponse }) {
  const isCredit = adj.amount >= 0;
  return (
    <tr className="border-b border-border-muted">
      <td className="py-2 pr-4 text-muted-foreground tabular-nums">
        {formatDate(adj.date)}
      </td>
      <td className="py-2 pr-4 text-foreground">{adj.merchant}</td>
      <td className="hidden py-2 pr-4 text-muted-foreground sm:table-cell">
        {adj.category}
      </td>
      <td
        className={`py-2 text-right tabular-nums ${isCredit ? "text-positive" : "text-negative"}`}
      >
        <span className="inline-flex items-center gap-1">
          {isCredit ? (
            <ArrowUpRight className="size-3.5" />
          ) : (
            <ArrowDownLeft className="size-3.5" />
          )}
          {formatCurrency(adj.amount)}
        </span>
      </td>
    </tr>
  );
}

export function AdjustmentExportDialog({
  open,
  onClose,
  year,
  month,
}: {
  open: boolean;
  onClose: () => void;
  year: number;
  month: number;
}) {
  const dialogRef = useDialogSync(open);
  const personId = useIdentityStore((s) => s.currentPersonId);

  const { data: personsResponse } = useGetPersons();
  const person = personsResponse?.data?.find((p) => p.id === personId);

  const {
    data: previewResponse,
    isLoading,
    error,
  } = usePreviewAdjustments(personId ?? "", year, month, {
    query: { enabled: open && personId != null },
  });
  const preview =
    previewResponse?.status === 200 ? previewResponse.data : undefined;

  const [isDownloading, setIsDownloading] = useState(false);
  const [successMessage, setSuccessMessage] = useTemporary<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const hasAccount = (person?.adjustment_account ?? "").trim() !== "";
  const monthLabel = `${MONTHS[month - 1]} ${year}`;

  const handleDownload = useCallback(async () => {
    if (!personId) return;
    setIsDownloading(true);
    setErrorMessage(null);
    try {
      const { rowCount } = await downloadAdjustmentCsv(personId, year, month);
      setSuccessMessage(`Downloaded ${plural("row", rowCount)}`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Download failed");
    } finally {
      setIsDownloading(false);
    }
  }, [personId, year, month, setSuccessMessage]);

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      className="mx-4 w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-lg backdrop:bg-black/40"
    >
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-medium text-foreground">
            Export Adjustments
          </h2>
          <p className="mt-0.5 text-sm text-muted-foreground">{monthLabel}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md p-1 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="mt-4">
        {!hasAccount && (
          <div className="rounded-lg border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
            <p>
              Set up your adjustment account in{" "}
              <Link
                to="/settings"
                onClick={onClose}
                className="font-medium text-primary underline underline-offset-2"
              >
                Settings
              </Link>{" "}
              to enable export.
            </p>
          </div>
        )}

        {hasAccount && isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {hasAccount && error && (
          <InlineError>
            {error instanceof Error ? error.message : "Failed to load preview"}
          </InlineError>
        )}

        {hasAccount && preview && preview.adjustments.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No adjustments for {monthLabel}.
          </p>
        )}

        {hasAccount && preview && preview.adjustments.length > 0 && (
          <>
            <p className="mb-3 text-sm text-muted-foreground">
              {preview.adjustment_count}{" "}
              {plural("adjustment", preview.adjustment_count)} for your Monarch
              account
            </p>
            <div className="max-h-64 overflow-y-auto overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-card">
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="px-3 py-2 font-medium">Date</th>
                    <th className="px-3 py-2 font-medium">Merchant</th>
                    <th className="hidden px-3 py-2 font-medium sm:table-cell">
                      Category
                    </th>
                    <th className="px-3 py-2 text-right font-medium">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.adjustments.map((adj) => (
                    <AdjustmentRow key={adj.dedup_id} adj={adj} />
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {errorMessage && (
          <div className="mt-3">
            <InlineError>{errorMessage}</InlineError>
          </div>
        )}
      </div>

      <div className="mt-5 flex items-center justify-end gap-3">
        {successMessage && (
          <span className="inline-flex items-center gap-1 text-sm text-positive">
            <Check className="size-4" />
            {successMessage}
          </span>
        )}
        <Button variant="secondary" size="sm" onClick={onClose}>
          Close
        </Button>
        {hasAccount && preview && preview.adjustments.length > 0 && (
          <Button
            size="sm"
            disabled={isDownloading}
            loading={isDownloading}
            loadingText="Downloading"
            icon={<Download className="size-4" />}
            onClick={handleDownload}
          >
            Download CSV
          </Button>
        )}
      </div>
    </dialog>
  );
}
