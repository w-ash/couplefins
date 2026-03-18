import {
  ArrowLeft,
  ArrowRight,
  Check,
  CircleAlert,
  Eye,
  Minus,
  Plus,
  Upload,
  Users,
} from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import type {
  ChangedTransactionResponse,
  PreviewUploadResponse,
} from "@/api/generated/model";
import { useGetPersons } from "@/api/generated/persons/persons";
import {
  usePostUpload,
  usePostUploadPreview,
} from "@/api/generated/uploads/uploads";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { UnmappedCategoriesWarning } from "@/components/UnmappedCategoriesWarning";
import { useSetToggle } from "@/hooks/useSetToggle";
import { useInvalidateCategories } from "@/lib/categories";
import {
  amountColorClass,
  formatCurrency,
  formatDate,
  formatSplit,
} from "@/lib/format";
import { useIdentityStore } from "@/lib/identity";
import { selectInputClass } from "@/lib/input-styles";

const PREVIEW_LIMIT = 5;

type Step = "form" | "preview" | "review" | "confirmed";

function ActionPanel({
  step,
  preview,
  acceptedIds,
  onConfirm,
  onBack,
  onToggleAll,
  isUploading,
}: {
  step: "preview" | "review";
  preview: PreviewUploadResponse;
  acceptedIds: Set<string>;
  onConfirm: () => void;
  onBack: () => void;
  onToggleAll: (accept: boolean) => void;
  isUploading: boolean;
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

      <UnmappedCategoriesWarning categories={preview.unmapped_categories} />

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
          loadingText="Importing..."
          icon={<Check className="size-4" />}
          fullWidth
        >
          Confirm Import
        </Button>
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

function PreviewCard({ preview }: { preview: PreviewUploadResponse }) {
  const visibleNew = preview.new_transactions.slice(0, PREVIEW_LIMIT);
  const remainingCount = Math.max(
    0,
    preview.new_transactions.length - PREVIEW_LIMIT,
  );

  return (
    <Card>
      <h2 className="mb-1 flex items-center gap-2 font-medium text-lg text-foreground">
        <Eye className="size-5" />
        Preview
      </h2>
      <p className="mb-4 text-sm text-muted-foreground">
        {preview.new_transactions.length} new transaction
        {preview.new_transactions.length !== 1 && "s"}
        {preview.unchanged_count > 0 &&
          `, ${preview.unchanged_count} unchanged`}
      </p>

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
              {tx.is_shared ? (
                <span className="inline-block rounded-full bg-primary-muted px-2 py-0.5 text-xs font-medium text-primary-muted-foreground">
                  Shared
                </span>
              ) : (
                <span className="inline-block rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                  Personal
                </span>
              )}
              {tx.is_shared && (
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
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="pb-2 pr-4 font-medium">Date</th>
              <th className="pb-2 pr-4 font-medium">Merchant</th>
              <th className="pb-2 pr-4 font-medium">Category</th>
              <th className="pb-2 pr-4 text-right font-medium">Amount</th>
              <th className="pb-2 pr-4 font-medium">Type</th>
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
                  {tx.is_shared ? (
                    <span className="inline-block rounded-full bg-primary-muted px-2 py-0.5 text-xs font-medium text-primary-muted-foreground">
                      Shared
                    </span>
                  ) : (
                    <span className="inline-block rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                      Personal
                    </span>
                  )}
                </td>
                <td className="py-2 text-muted-foreground tabular-nums">
                  {tx.is_shared ? (
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
          and {remainingCount} more transaction
          {remainingCount !== 1 && "s"}
        </p>
      )}
    </Card>
  );
}

export function UploadPage() {
  const invalidateCategories = useInvalidateCategories();
  const currentPersonId = useIdentityStore((s) => s.currentPersonId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [personId, setPersonId] = useState(currentPersonId ?? "");
  useEffect(() => {
    if (currentPersonId) setPersonId(currentPersonId);
  }, [currentPersonId]);
  const [step, setStep] = useState<Step>("form");
  const {
    selected: acceptedIds,
    toggle: toggleAccepted,
    setAll: setAllAccepted,
    clear: clearAccepted,
  } = useSetToggle();

  const { data: personsResponse } = useGetPersons();
  const persons = personsResponse?.data;

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
        setStep("confirmed");
      },
    },
  });

  function buildFormData(): { file: Blob; person_id: string } | null {
    const file = fileInputRef.current?.files?.[0];
    if (!file || !personId) return null;
    return { file, person_id: personId };
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

  function handleReset() {
    setStep("form");
    previewMutation.reset();
    uploadMutation.reset();
    clearAccepted();
    setPersonId(currentPersonId ?? "");
    if (fileInputRef.current) fileInputRef.current.value = "";
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
      className={`mx-auto px-6 py-12 ${showGrid ? "max-w-3xl md:max-w-5xl" : "max-w-3xl"}`}
    >
      <PageHeader
        icon={<Upload className="size-6" />}
        title="Upload Transactions"
      />

      <Card as="form" onSubmit={handlePreview} className="space-y-6">
        {/* Person selector */}
        <div>
          <label
            htmlFor={
              currentPersonId && personId === currentPersonId
                ? undefined
                : "person"
            }
            className="mb-1.5 flex items-center gap-1.5 font-medium text-sm text-secondary-foreground"
          >
            <Users className="size-4" />
            Who are you?
          </label>
          {currentPersonId && personId === currentPersonId ? (
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded-full bg-accent px-3 py-1.5 text-sm font-medium text-accent-foreground">
                {persons?.find((p) => p.id === currentPersonId)?.name ??
                  "Unknown"}
              </span>
              {!isFormDisabled && (
                <button
                  type="button"
                  onClick={() => setPersonId("")}
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  Change
                </button>
              )}
            </div>
          ) : (
            <select
              id="person"
              value={personId}
              onChange={(e) => setPersonId(e.target.value)}
              required
              disabled={isFormDisabled}
              className={`w-full min-h-11 ${selectInputClass} disabled:cursor-not-allowed disabled:opacity-50`}
            >
              <option value="">Select person...</option>
              {persons?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* File input */}
        <div>
          <label
            htmlFor="csv-file"
            className="mb-1.5 block font-medium text-sm text-secondary-foreground"
          >
            Monarch CSV
          </label>
          <input
            id="csv-file"
            ref={fileInputRef}
            type="file"
            accept=".csv"
            required
            disabled={isFormDisabled}
            className="w-full min-h-11 rounded-lg border border-input bg-card px-3 py-2 text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-accent file:px-3 file:py-1 file:font-medium file:text-sm file:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
          />
        </div>

        {/* Submit */}
        {step === "form" && (
          <Button
            type="submit"
            disabled={!personId}
            loading={previewMutation.isPending}
            loadingText="Parsing..."
            icon={<Eye className="size-4" />}
            fullWidth
          >
            Preview CSV
          </Button>
        )}
      </Card>

      {/* Error */}
      <div aria-live="polite" aria-atomic="true">
        {error && (
          <div
            role="alert"
            className="mt-4 flex items-start gap-2.5 rounded-lg border border-destructive-border bg-destructive-muted p-4 text-sm text-destructive-muted-foreground"
          >
            <CircleAlert className="mt-0.5 size-4 shrink-0" />
            {error instanceof Error ? error.message : "An error occurred"}
          </div>
        )}
      </div>

      {/* Already up to date */}
      {step === "preview" && preview && nothingToImport && (
        <Card className="mt-6">
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
        <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-[1fr_16rem]">
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
          />
        </div>
      )}

      {/* Confirmed summary */}
      {step === "confirmed" && summary && (
        <Card aria-live="polite" className="mt-6">
          <h2 className="mb-4 flex items-center gap-2 font-medium text-lg text-foreground">
            <Check className="size-5 text-primary" />
            Upload Complete
          </h2>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <dt className="text-muted-foreground">New</dt>
            <dd className="font-medium text-foreground tabular-nums">
              {summary.new_count}
            </dd>
            <dt className="text-muted-foreground">Updated</dt>
            <dd className="font-medium text-accent-foreground tabular-nums">
              {summary.updated_count}
            </dd>
            <dt className="text-muted-foreground">Skipped</dt>
            <dd className="font-medium text-muted-foreground tabular-nums">
              {summary.skipped_count}
            </dd>
          </dl>

          <UnmappedCategoriesWarning
            categories={summary.unmapped_categories}
            className="mt-4"
          />

          <Button
            type="button"
            variant="secondary"
            onClick={handleReset}
            icon={<Plus className="size-4" />}
            fullWidth
            className="mt-6"
          >
            Upload Another CSV
          </Button>
        </Card>
      )}
    </div>
  );
}
