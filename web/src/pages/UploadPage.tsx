import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CircleAlert,
  Eye,
  ListChecks,
  Minus,
  Plus,
  Upload,
} from "lucide-react";
import { type FormEvent, useRef, useState } from "react";
import { Link } from "react-router";
import type {
  ChangedTransactionResponse,
  PersonResponse,
  PreviewUploadResponse,
  UploadHistoryEntryResponse,
  UploadSummaryResponse,
} from "@/api/generated/model";
import { useGetPersons } from "@/api/generated/persons/persons";
import {
  getUploadHistoryQueryKey,
  usePostUpload,
  usePostUploadPreview,
  useUploadHistory,
} from "@/api/generated/uploads/uploads";
import { AnimatedCheck } from "@/components/AnimatedCheck";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { FileDropZone } from "@/components/FileDropZone";
import { PageHeader } from "@/components/PageHeader";
import { ProgressBar } from "@/components/ProgressBar";
import { StepIndicator } from "@/components/StepIndicator";
import { TagReferenceGuide } from "@/components/TagReferenceGuide";
import { UnmappedCategoriesWarning } from "@/components/UnmappedCategoriesWarning";
import { UploadError } from "@/components/UploadError";
import { UploadHistory } from "@/components/UploadHistory";
import { useSetToggle } from "@/hooks/useSetToggle";
import { useUploadProgress } from "@/hooks/useUploadProgress";
import { useInvalidateCategories } from "@/lib/categories";
import { validateCsvHeaders } from "@/lib/csv-validation";
import {
  amountColorClass,
  formatCurrency,
  formatDate,
  formatSplit,
  MONTHS,
  plural,
} from "@/lib/format";
import { useIdentityStore } from "@/lib/identity";
import { PAGE_PADDING, tableHeaderRowClass } from "@/lib/layout";

const PREVIEW_LIMIT = 5;
const MAX_CSV_SIZE = 10 * 1024 * 1024;

type Step = "form" | "preview" | "review" | "confirmed";

function stepToIndex(step: Step): number {
  if (step === "form") return 0;
  if (step === "preview" || step === "review") return 1;
  return 2;
}

function deriveUploadMonth(
  preview: PreviewUploadResponse | undefined,
): { year: number; month: number } | null {
  const dateStr =
    preview?.new_transactions[0]?.date ??
    preview?.changed_transactions[0]?.incoming.date;
  if (!dateStr) return null;
  const [yearStr, monthStr] = dateStr.split("-");
  return { year: Number(yearStr), month: Number(monthStr) };
}

function ActionPanel({
  step,
  preview,
  acceptedIds,
  onConfirm,
  onBack,
  onToggleAll,
  isUploading,
  progress,
}: {
  step: "preview" | "review";
  preview: PreviewUploadResponse;
  acceptedIds: Set<string>;
  onConfirm: () => void;
  onBack: () => void;
  onToggleAll: (accept: boolean) => void;
  isUploading: boolean;
  progress: { current: number; total: number; detail: string } | null;
}) {
  const totalChanged = preview.changed_transactions.length;

  return (
    <aside className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-sm md:sticky md:top-6 md:self-start">
      <dl className="grid grid-cols-2 gap-y-2 text-sm">
        {preview.new_transactions.length > 0 && (
          <>
            <dt className="text-muted-foreground">New</dt>
            <dd className="text-right font-medium text-foreground tabular-nums">
              {preview.new_transactions.length}
            </dd>
          </>
        )}
        {step === "review" && totalChanged > 0 && (
          <>
            <dt className="text-muted-foreground">Changed</dt>
            <dd className="text-right font-medium text-accent-foreground tabular-nums">
              {totalChanged}
            </dd>
          </>
        )}
        {preview.unchanged_count > 0 && (
          <>
            <dt className="text-muted-foreground">Unchanged</dt>
            <dd className="text-right font-medium text-muted-foreground tabular-nums">
              {preview.unchanged_count}
            </dd>
          </>
        )}
      </dl>

      <UnmappedCategoriesWarning
        categories={preview.unmapped_categories}
        compact
      />

      {step === "review" && totalChanged > 0 && (
        <>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onToggleAll(true)}
            >
              Accept All
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onToggleAll(false)}
            >
              Reject All
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            {acceptedIds.size} of {totalChanged} accepted
          </p>
        </>
      )}

      <div className="space-y-2 border-t border-border pt-4">
        <Button
          type="button"
          onClick={onConfirm}
          loading={isUploading}
          loadingText="Importing…"
          icon={<Check className="size-4" />}
          fullWidth
        >
          Confirm Import
        </Button>
        {isUploading && progress && (
          <div className="space-y-1.5">
            <ProgressBar pct={(progress.current / progress.total) * 100} />
            <p className="text-center text-xs text-muted-foreground">
              {progress.detail}
            </p>
          </div>
        )}
        <Button
          type="button"
          variant="secondary"
          onClick={onBack}
          disabled={isUploading}
          icon={<ArrowLeft className="size-4" />}
          fullWidth
        >
          Back
        </Button>
      </div>
    </aside>
  );
}

function typeBreakdown(transactions: { household: boolean }[]): string {
  let householdCount = 0;
  let personalCount = 0;
  for (const tx of transactions) {
    if (tx.household) householdCount++;
    else personalCount++;
  }
  const parts: string[] = [];
  if (householdCount) parts.push(`${householdCount} household`);
  if (personalCount) parts.push(`${personalCount} personal`);
  return parts.join(", ");
}

function ScopeBadge({ household }: { household: boolean }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
        household
          ? "bg-primary-muted text-primary-muted-foreground"
          : "bg-muted/50 text-muted-foreground/50"
      }`}
    >
      {household ? "Household" : "Personal"}
    </span>
  );
}

function PreviewCard({ preview }: { preview: PreviewUploadResponse }) {
  const visibleNew = preview.new_transactions.slice(0, PREVIEW_LIMIT);
  const remainingCount = Math.max(
    0,
    preview.new_transactions.length - PREVIEW_LIMIT,
  );
  const breakdown = typeBreakdown(preview.new_transactions);

  return (
    <Card>
      <h2 className="mb-1 flex items-center gap-2 font-medium text-lg text-foreground">
        <Eye className="size-5" />
        Preview
      </h2>
      <p className="mb-1 text-sm text-muted-foreground">
        {plural("new transaction", preview.new_transactions.length)}
        {preview.unchanged_count > 0 &&
          `, ${preview.unchanged_count} unchanged`}
      </p>
      {breakdown && (
        <p className="mb-4 text-xs text-muted-foreground">{breakdown}</p>
      )}

      {/* Mobile: card layout */}
      <div className="space-y-3 sm:hidden">
        {visibleNew.map((tx, i) => (
          <div
            // biome-ignore lint/suspicious/noArrayIndexKey: static preview rows, never reordered
            key={i}
            className="rounded-lg border border-border-muted p-3"
          >
            <div className="flex items-center justify-between">
              <span className="font-medium text-foreground">{tx.merchant}</span>
              <span className={`tabular-nums ${amountColorClass(tx.amount)}`}>
                {formatCurrency(tx.amount)}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span className="tabular-nums">{formatDate(tx.date)}</span>
              <span>{tx.category}</span>
              <ScopeBadge household={tx.household} />
              {tx.household && tx.payer_percentage < 100 && (
                <span className="tabular-nums">
                  {formatSplit(tx.payer_percentage)}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Desktop: table layout */}
      <div className="hidden overflow-x-auto sm:block">
        <table className="w-full text-sm">
          <thead>
            <tr className={tableHeaderRowClass}>
              <th className="pb-2 pr-4 font-medium">Date</th>
              <th className="pb-2 pr-4 font-medium">Merchant</th>
              <th className="pb-2 pr-4 font-medium">Category</th>
              <th className="pb-2 pr-4 text-right font-medium">Amount</th>
              <th className="pb-2 pr-4 font-medium">Scope</th>
              <th className="pb-2 font-medium">Split</th>
            </tr>
          </thead>
          <tbody>
            {visibleNew.map((tx, i) => (
              <tr
                // biome-ignore lint/suspicious/noArrayIndexKey: static preview rows, never reordered
                key={i}
                className="border-b border-border-muted"
              >
                <td className="py-2 pr-4 text-muted-foreground tabular-nums">
                  {formatDate(tx.date)}
                </td>
                <td className="py-2 pr-4 text-foreground">{tx.merchant}</td>
                <td className="py-2 pr-4 text-muted-foreground">
                  {tx.category}
                </td>
                <td
                  className={`py-2 pr-4 text-right tabular-nums ${amountColorClass(tx.amount)}`}
                >
                  {formatCurrency(tx.amount)}
                </td>
                <td className="py-2 pr-4">
                  <ScopeBadge household={tx.household} />
                </td>
                <td className="py-2 text-muted-foreground tabular-nums">
                  {tx.household && tx.payer_percentage < 100 ? (
                    formatSplit(tx.payer_percentage)
                  ) : (
                    <Minus className="size-4 text-icon-muted" />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {remainingCount > 0 && (
        <p className="mt-3 text-center text-sm text-muted-foreground">
          and {plural("more transaction", remainingCount)}
        </p>
      )}
    </Card>
  );
}

function ConfirmedCard({
  summary,
  preview,
  personId,
  persons,
  historyEntries,
  onReset,
}: {
  summary: UploadSummaryResponse;
  preview: PreviewUploadResponse | undefined;
  personId: string;
  persons: PersonResponse[] | undefined;
  historyEntries: UploadHistoryEntryResponse[];
  onReset: () => void;
}) {
  const uploadMonth = deriveUploadMonth(preview);
  const monthLabel = uploadMonth
    ? `${MONTHS[uploadMonth.month - 1]} ${uploadMonth.year}`
    : null;

  const householdCount = preview
    ? preview.new_transactions.filter((tx) => tx.household).length +
      preview.changed_transactions.filter((ct) => ct.incoming.household).length
    : summary.new_count + summary.updated_count;

  const partner = persons?.find((p) => p.id !== personId);
  const partnerHasUploaded =
    !partner || !uploadMonth
      ? true
      : historyEntries.some((e) => {
          if (e.person_id === personId) return false;
          if (!e.date_range_start) return false;
          const [y, m] = e.date_range_start.split("-");
          return (
            Number(y) === uploadMonth.year && Number(m) === uploadMonth.month
          );
        });

  // Partner prompt requires uploadMonth too, so this simplifies to just uploadMonth
  const hasNextSteps = uploadMonth !== null;

  return (
    <Card aria-live="polite" className="step-enter mt-6">
      {/* Success header */}
      <div className="flex items-center gap-3">
        <AnimatedCheck size={40} />
        <div>
          <h2 className="font-medium text-lg text-foreground">
            Upload Complete
          </h2>
          {monthLabel && (
            <p className="text-sm text-muted-foreground">
              {plural("household transaction", householdCount)} for {monthLabel}
            </p>
          )}
        </div>
      </div>

      {/* Stats grid */}
      <dl className="mt-5 grid grid-cols-3 gap-4 text-sm">
        <div className="flex flex-col-reverse text-center">
          <dt className="text-muted-foreground">New</dt>
          <dd className="text-lg font-semibold text-foreground tabular-nums">
            {summary.new_count}
          </dd>
        </div>
        <div className="flex flex-col-reverse text-center">
          <dt className="text-muted-foreground">Updated</dt>
          <dd className="text-lg font-semibold text-accent-foreground tabular-nums">
            {summary.updated_count}
          </dd>
        </div>
        <div className="flex flex-col-reverse text-center">
          <dt className="text-muted-foreground">Skipped</dt>
          <dd className="text-lg font-semibold text-muted-foreground tabular-nums">
            {summary.skipped_count}
          </dd>
        </div>
      </dl>

      <UnmappedCategoriesWarning
        categories={summary.unmapped_categories}
        className="mt-4"
      />

      {/* Next steps */}
      {hasNextSteps && (
        <div className="mt-5 space-y-1 border-t border-border pt-5">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Next steps
          </p>
          {uploadMonth && (
            <Link
              to={`/transactions?year=${uploadMonth.year}&month=${uploadMonth.month}`}
              className="flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm text-foreground transition-colors hover:bg-muted/50"
            >
              <ListChecks className="size-4 text-muted-foreground" />
              <span className="flex-1">Review transactions</span>
              <ArrowRight className="size-4 text-muted-foreground" />
            </Link>
          )}
          {!partnerHasUploaded && partner && (
            <button
              type="button"
              onClick={onReset}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm text-foreground transition-colors hover:bg-muted/50"
            >
              <Upload className="size-4 text-muted-foreground" />
              <span className="flex-1">Upload {partner.name}'s CSV</span>
              <ArrowRight className="size-4 text-muted-foreground" />
            </button>
          )}
        </div>
      )}

      <Button
        type="button"
        variant="secondary"
        onClick={onReset}
        icon={<Plus className="size-4" />}
        fullWidth
        className="mt-5"
      >
        Upload Another CSV
      </Button>
    </Card>
  );
}

export function UploadPage() {
  const queryClient = useQueryClient();
  const invalidateCategories = useInvalidateCategories();
  const personId = useIdentityStore((s) => s.currentPersonId) ?? "";
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [headerError, setHeaderError] = useState<string | null>(null);
  const [step, setStep] = useState<Step>("form");
  const {
    selected: acceptedIds,
    toggle: toggleAccepted,
    setAll: setAllAccepted,
    clear: clearAccepted,
  } = useSetToggle();

  const { data: personsResponse } = useGetPersons();
  const persons = personsResponse?.data;
  const { data: historyResponse } = useUploadHistory();

  const previewMutation = usePostUploadPreview({
    mutation: {
      onSuccess: (response) => {
        if (response.status !== 200) return;
        const data = response.data;
        if (data.changed_transactions.length > 0) {
          setAllAccepted(
            data.changed_transactions.map(
              (ct: ChangedTransactionResponse) => ct.existing_id,
            ),
          );
          setStep("review");
        } else {
          setStep("preview");
        }
      },
    },
  });

  const uploadMutation = usePostUpload({
    mutation: {
      onSuccess: () => {
        invalidateCategories();
        queryClient.invalidateQueries({
          queryKey: getUploadHistoryQueryKey(),
        });
        setStep("confirmed");
      },
    },
  });

  const uploadProgress = useUploadProgress(uploadMutation.isPending);

  function buildFormData(): { file: Blob } | null {
    if (!selectedFile) return null;
    return { file: selectedFile };
  }

  function handlePreview(e: FormEvent) {
    e.preventDefault();
    const body = buildFormData();
    if (!body) return;
    previewMutation.mutate({ data: body });
  }

  function handleConfirm() {
    const body = buildFormData();
    if (!body) return;
    uploadMutation.mutate({
      data: {
        ...body,
        accepted_change_ids: JSON.stringify(Array.from(acceptedIds)),
      },
    });
  }

  function handleBack() {
    if (step === "review") {
      setStep("preview");
    } else {
      setStep("form");
      previewMutation.reset();
    }
  }

  const validatingFileRef = useRef<File | null>(null);

  function handleFileSelected(file: File) {
    setSelectedFile(file);
    setHeaderError(null);
    previewMutation.reset();
    validatingFileRef.current = file;
    validateCsvHeaders(file).then((error) => {
      if (validatingFileRef.current !== file) return;
      if (error) setHeaderError(error);
    });
  }

  function handleReset() {
    setStep("form");
    previewMutation.reset();
    uploadMutation.reset();
    clearAccepted();
    setSelectedFile(null);
    setHeaderError(null);
  }

  function toggleAll(accept: boolean) {
    if (accept && preview) {
      setAllAccepted(preview.changed_transactions.map((ct) => ct.existing_id));
    } else {
      clearAccepted();
    }
  }

  const isFormDisabled = step !== "form";
  const preview =
    previewMutation.data?.status === 200
      ? previewMutation.data.data
      : undefined;
  const summary =
    uploadMutation.data?.status === 201 ? uploadMutation.data.data : undefined;
  const error = previewMutation.error || uploadMutation.error;

  const hasNewTransactions = preview && preview.new_transactions.length > 0;
  const hasChanges = preview && preview.changed_transactions.length > 0;
  const nothingToImport = preview && !hasNewTransactions && !hasChanges;
  const actionStep =
    (step === "preview" || step === "review") && !nothingToImport ? step : null;
  const showGrid = actionStep !== null && preview;

  return (
    <div
      className={`mx-auto ${PAGE_PADDING} ${showGrid ? "max-w-3xl md:max-w-5xl" : "max-w-3xl"}`}
    >
      <PageHeader
        icon={<Upload className="size-6" />}
        title="Upload Transactions"
      />

      <StepIndicator currentStepIndex={stepToIndex(step)} />

      <Card as="form" onSubmit={handlePreview} className="space-y-6">
        {/* File drop zone */}
        <div>
          <span className="mb-1.5 block font-medium text-sm text-secondary-foreground">
            Monarch CSV
          </span>
          <FileDropZone
            accept=".csv"
            onFile={handleFileSelected}
            disabled={isFormDisabled}
            currentFile={selectedFile}
            maxSizeBytes={MAX_CSV_SIZE}
          />
          {headerError && (
            <div
              role="alert"
              className="mt-2 flex items-start gap-2 rounded-lg border border-destructive-border bg-destructive-muted p-3 text-sm text-destructive-muted-foreground"
            >
              <CircleAlert className="mt-0.5 size-4 shrink-0" />
              {headerError}
            </div>
          )}
        </div>

        {/* Submit */}
        {step === "form" && (
          <Button
            type="submit"
            disabled={!selectedFile || !!headerError}
            loading={previewMutation.isPending}
            loadingText="Previewing…"
            icon={<Eye className="size-4" />}
            fullWidth
          >
            Preview CSV
          </Button>
        )}
      </Card>

      {/* Error */}
      <div aria-live="polite" aria-atomic="true">
        {error && <UploadError error={error} />}
      </div>

      {step === "form" && <TagReferenceGuide />}

      {/* Already up to date */}
      {step === "preview" && preview && nothingToImport && (
        <Card className="step-enter mt-6">
          <h2 className="mb-1 flex items-center gap-2 font-medium text-lg text-foreground">
            <Eye className="size-5" />
            Already Up to Date
          </h2>
          <p className="mt-3 text-sm text-muted-foreground">
            All transactions already imported — you're up to date.
          </p>
          <Button
            type="button"
            variant="secondary"
            onClick={handleReset}
            icon={<ArrowLeft className="size-4" />}
            fullWidth
            className="mt-6"
          >
            Back
          </Button>
        </Card>
      )}

      {/* Preview / Review — two-column grid */}
      {showGrid && (
        <div
          key={step}
          className="step-enter mt-6 grid grid-cols-1 gap-6 md:grid-cols-[1fr_16rem]"
        >
          {/* Left column — content */}
          <div className="space-y-6">
            {/* Preview summary + capped transaction table */}
            {step === "preview" && hasNewTransactions && (
              <PreviewCard preview={preview} />
            )}

            {/* Review — changed transactions with checkboxes */}
            {step === "review" && hasChanges && (
              <Card>
                <h2 className="mb-4 flex items-center gap-2 font-medium text-lg text-foreground">
                  <Eye className="size-5" />
                  Review Changes
                </h2>
                <div className="space-y-3">
                  {preview.changed_transactions.map((ct) => (
                    <label
                      key={ct.existing_id}
                      className="flex cursor-pointer items-start gap-3 rounded-lg border border-border-muted p-4 transition-colors hover:bg-muted/50"
                    >
                      <input
                        type="checkbox"
                        checked={acceptedIds.has(ct.existing_id)}
                        onChange={() => toggleAccepted(ct.existing_id)}
                        className="mt-0.5 size-4 rounded border-input accent-primary"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2 text-sm">
                          <span className="font-medium text-foreground">
                            {ct.incoming.merchant}
                          </span>
                          <span className="text-muted-foreground tabular-nums">
                            {formatDate(ct.incoming.date)}
                          </span>
                          <span
                            className={`tabular-nums ${amountColorClass(ct.incoming.amount)}`}
                          >
                            {formatCurrency(ct.incoming.amount)}
                          </span>
                        </div>
                        <div className="mt-1.5 space-y-1">
                          {ct.diffs.map((d) => (
                            <div
                              key={d.field_name}
                              className="flex flex-wrap gap-2 text-xs text-muted-foreground"
                            >
                              <span className="font-medium min-w-[5rem]">
                                {d.field_name}:
                              </span>
                              <span className="inline-flex items-center gap-0.5 line-through text-negative/70">
                                {d.old_value || "(empty)"}
                              </span>
                              <ArrowRight className="size-3 shrink-0 text-muted-foreground" />
                              <span className="inline-flex items-center gap-0.5 text-positive">
                                {d.new_value || "(empty)"}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </Card>
            )}
          </div>

          {/* Right column — sticky action panel */}
          <ActionPanel
            step={actionStep}
            preview={preview}
            acceptedIds={acceptedIds}
            onConfirm={handleConfirm}
            onBack={handleBack}
            onToggleAll={toggleAll}
            isUploading={uploadMutation.isPending}
            progress={uploadProgress}
          />
        </div>
      )}

      {/* Confirmed summary */}
      {step === "confirmed" && summary && (
        <ConfirmedCard
          summary={summary}
          preview={preview}
          personId={personId}
          persons={persons}
          historyEntries={
            historyResponse?.status === 200 ? historyResponse.data.entries : []
          }
          onReset={handleReset}
        />
      )}

      <UploadHistory />
    </div>
  );
}
