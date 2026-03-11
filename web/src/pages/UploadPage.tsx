import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  CircleAlert,
  Eye,
  Loader2,
  Minus,
  Plus,
  Upload,
  Users,
} from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { UnmappedCategoriesWarning } from "@/components/UnmappedCategoriesWarning";
import { apiFetch } from "@/lib/api";
import { useInvalidateCategories } from "@/lib/categories";
import { formatCurrency, formatDate, formatSplit } from "@/lib/format";
import { useIdentityStore } from "@/lib/identity";
import { fetchPersons, PERSONS_QUERY_KEY } from "@/types/person";

interface PreviewTransaction {
  date: string;
  merchant: string;
  category: string;
  amount: number;
  is_shared: boolean;
  payer_percentage: number | null;
}

interface FieldDiff {
  field_name: string;
  old_value: string;
  new_value: string;
}

interface ChangedTransaction {
  existing_id: string;
  incoming: PreviewTransaction;
  existing: PreviewTransaction;
  diffs: FieldDiff[];
}

interface PreviewData {
  new_transactions: PreviewTransaction[];
  unchanged_count: number;
  changed_transactions: ChangedTransaction[];
  unmapped_categories: string[];
}

interface UploadSummary {
  upload_id: string;
  filename: string;
  new_count: number;
  updated_count: number;
  skipped_count: number;
  unmapped_categories: string[];
}

type Step = "form" | "preview" | "review" | "confirmed";

function previewCsv(formData: FormData): Promise<PreviewData> {
  return apiFetch("/api/v1/uploads/preview", {
    method: "POST",
    body: formData,
  });
}

function uploadCsv(formData: FormData): Promise<UploadSummary> {
  return apiFetch("/api/v1/uploads/", {
    method: "POST",
    body: formData,
  });
}

export function UploadPage() {
  const queryClient = useQueryClient();
  const invalidateCategories = useInvalidateCategories();
  const currentPersonId = useIdentityStore((s) => s.currentPersonId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [personId, setPersonId] = useState(currentPersonId ?? "");
  useEffect(() => {
    if (currentPersonId) setPersonId(currentPersonId);
  }, [currentPersonId]);
  const [step, setStep] = useState<Step>("form");
  const [acceptedIds, setAcceptedIds] = useState<Set<string>>(new Set());

  const personsQuery = useQuery({
    queryKey: PERSONS_QUERY_KEY,
    queryFn: fetchPersons,
  });

  const previewMutation = useMutation({
    mutationFn: previewCsv,
    onSuccess: (data) => {
      if (data.changed_transactions.length > 0) {
        // Default all checked
        setAcceptedIds(
          new Set(data.changed_transactions.map((ct) => ct.existing_id)),
        );
        setStep("review");
      } else {
        setStep("preview");
      }
    },
  });

  const uploadMutation = useMutation({
    mutationFn: uploadCsv,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["uploads"] });
      invalidateCategories();
      setStep("confirmed");
    },
  });

  function buildFormData(): FormData | null {
    const file = fileInputRef.current?.files?.[0];
    if (!file || !personId) return null;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("person_id", personId);
    return formData;
  }

  function handlePreview(e: FormEvent) {
    e.preventDefault();
    const formData = buildFormData();
    if (!formData) return;
    previewMutation.mutate(formData);
  }

  function handleConfirm() {
    const formData = buildFormData();
    if (!formData) return;
    formData.append(
      "accepted_change_ids",
      JSON.stringify(Array.from(acceptedIds)),
    );
    uploadMutation.mutate(formData);
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
    setAcceptedIds(new Set());
    setPersonId("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function toggleAccepted(id: string) {
    setAcceptedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll(accept: boolean) {
    if (accept && preview) {
      setAcceptedIds(
        new Set(preview.changed_transactions.map((ct) => ct.existing_id)),
      );
    } else {
      setAcceptedIds(new Set());
    }
  }

  const isFormDisabled = step !== "form";
  const preview = previewMutation.data;
  const summary = uploadMutation.data;
  const error = previewMutation.error || uploadMutation.error;

  const hasNewTransactions = preview && preview.new_transactions.length > 0;
  const hasChanges = preview && preview.changed_transactions.length > 0;
  const nothingToImport = preview && !hasNewTransactions && !hasChanges;

  const confirmBackFooter = (
    <div className="mt-6 flex gap-3">
      <button
        type="button"
        onClick={handleConfirm}
        disabled={uploadMutation.isPending}
        className="flex min-h-11 flex-1 items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {uploadMutation.isPending ? (
          <>
            <Loader2 className="size-4 animate-spin" />
            Importing...
          </>
        ) : (
          <>
            <Check className="size-4" />
            Confirm Import
          </>
        )}
      </button>
      <button
        type="button"
        onClick={handleBack}
        disabled={uploadMutation.isPending}
        className="flex items-center gap-2 rounded-lg border border-input bg-card px-4 py-2.5 font-medium text-secondary-foreground shadow-sm transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
      >
        <ArrowLeft className="size-4" />
        Back
      </button>
    </div>
  );

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="mb-8 flex items-center gap-2.5 font-semibold text-2xl text-foreground">
        <Upload className="size-6" />
        Upload Transactions
      </h1>

      <form
        onSubmit={handlePreview}
        className="space-y-6 rounded-xl border border-border bg-card p-6 shadow-sm"
      >
        {/* Person selector */}
        <div>
          <label
            htmlFor="person"
            className="mb-1.5 flex items-center gap-1.5 font-medium text-sm text-secondary-foreground"
          >
            <Users className="size-4" />
            Who are you?
          </label>
          <select
            id="person"
            value={personId}
            onChange={(e) => setPersonId(e.target.value)}
            required
            disabled={isFormDisabled}
            className="w-full rounded-lg border border-input bg-card px-3 py-2 text-foreground shadow-sm focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          >
            <option value="">Select person...</option>
            {personsQuery.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
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
            className="w-full rounded-lg border border-input bg-card px-3 py-2 text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-accent file:px-3 file:py-1 file:font-medium file:text-sm file:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50"
          />
        </div>

        {/* Submit */}
        {step === "form" && (
          <button
            type="submit"
            disabled={previewMutation.isPending || !personId}
            className="flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {previewMutation.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Parsing...
              </>
            ) : (
              <>
                <Eye className="size-4" />
                Preview
              </>
            )}
          </button>
        )}
      </form>

      {/* Error */}
      <div aria-live="polite" aria-atomic="true">
        {error && (
          <div
            role="alert"
            className="mt-4 flex items-start gap-2.5 rounded-lg border border-destructive-border bg-destructive-muted p-4 text-sm text-destructive-muted-foreground"
          >
            <CircleAlert className="mt-0.5 size-4 shrink-0" />
            {error.message}
          </div>
        )}
      </div>

      {/* Preview — summary only (no full table) */}
      {step === "preview" && preview && (
        <div className="mt-6 rounded-xl border border-border bg-card p-6 shadow-sm">
          <h2 className="mb-1 flex items-center gap-2 font-medium text-lg text-foreground">
            <Eye className="size-5" />
            Preview
          </h2>

          {nothingToImport ? (
            <p className="mt-3 text-sm text-muted-foreground">
              All transactions already imported. Nothing to do.
            </p>
          ) : (
            <>
              <p className="mb-4 text-sm text-muted-foreground">
                {preview.new_transactions.length} new transaction
                {preview.new_transactions.length !== 1 && "s"}
                {preview.unchanged_count > 0 &&
                  `, ${preview.unchanged_count} unchanged`}
              </p>

              <UnmappedCategoriesWarning
                categories={preview.unmapped_categories}
                className="mb-4"
              />

              {/* New transactions table */}
              {hasNewTransactions && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="pb-2 pr-4 font-medium">Date</th>
                        <th className="pb-2 pr-4 font-medium">Merchant</th>
                        <th className="pb-2 pr-4 font-medium">Category</th>
                        <th className="pb-2 pr-4 text-right font-medium">
                          Amount
                        </th>
                        <th className="pb-2 pr-4 font-medium">Type</th>
                        <th className="pb-2 font-medium">Split</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.new_transactions.map((tx, i) => (
                        // biome-ignore lint/suspicious/noArrayIndexKey: static preview rows, never reordered
                        <tr key={i} className="border-b border-border-muted">
                          <td className="py-2 pr-4 text-muted-foreground tabular-nums">
                            {formatDate(tx.date)}
                          </td>
                          <td className="py-2 pr-4 text-foreground">
                            {tx.merchant}
                          </td>
                          <td className="py-2 pr-4 text-muted-foreground">
                            {tx.category}
                          </td>
                          <td
                            className={`py-2 pr-4 text-right tabular-nums ${tx.amount < 0 ? "text-negative" : "text-positive"}`}
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
              )}

              {confirmBackFooter}
            </>
          )}

          {nothingToImport && (
            <button
              type="button"
              onClick={handleReset}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg border border-input bg-card px-4 py-2.5 font-medium text-secondary-foreground shadow-sm transition-colors hover:bg-muted"
            >
              <ArrowLeft className="size-4" />
              Back
            </button>
          )}
        </div>
      )}

      {/* Review changed transactions */}
      {step === "review" && preview && hasChanges && (
        <div className="mt-6 rounded-xl border border-border bg-card p-6 shadow-sm">
          <h2 className="mb-1 flex items-center gap-2 font-medium text-lg text-foreground">
            <Eye className="size-5" />
            Review Changes
          </h2>
          <p className="mb-4 text-sm text-muted-foreground">
            {preview.changed_transactions.length} transaction
            {preview.changed_transactions.length !== 1 && "s"} changed since
            last upload.
            {preview.new_transactions.length > 0 &&
              ` ${preview.new_transactions.length} new will also be imported.`}
            {preview.unchanged_count > 0 &&
              ` ${preview.unchanged_count} unchanged.`}
          </p>

          <UnmappedCategoriesWarning
            categories={preview.unmapped_categories}
            className="mb-4"
          />

          {/* Accept/Reject all */}
          <div className="mb-4 flex gap-2">
            <button
              type="button"
              onClick={() => toggleAll(true)}
              className="rounded-full px-3 py-1 text-sm font-medium bg-primary-muted text-primary-muted-foreground transition-colors hover:bg-primary-muted/80"
            >
              Accept All
            </button>
            <button
              type="button"
              onClick={() => toggleAll(false)}
              className="rounded-full px-3 py-1 text-sm font-medium bg-muted text-muted-foreground transition-colors hover:bg-secondary"
            >
              Reject All
            </button>
          </div>

          {/* Changed transactions list */}
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
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-medium text-foreground">
                      {ct.incoming.merchant}
                    </span>
                    <span className="text-muted-foreground tabular-nums">
                      {formatDate(ct.incoming.date)}
                    </span>
                    <span
                      className={`tabular-nums ${ct.incoming.amount < 0 ? "text-negative" : "text-positive"}`}
                    >
                      {formatCurrency(ct.incoming.amount)}
                    </span>
                  </div>
                  <div className="mt-1.5 space-y-1">
                    {ct.diffs.map((d) => (
                      <div
                        key={d.field_name}
                        className="flex gap-2 text-xs text-muted-foreground"
                      >
                        <span className="font-medium min-w-[5rem]">
                          {d.field_name}:
                        </span>
                        <span className="line-through text-negative/70">
                          {d.old_value || "(empty)"}
                        </span>
                        <span className="text-positive">
                          {d.new_value || "(empty)"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </label>
            ))}
          </div>

          {confirmBackFooter}
        </div>
      )}

      {/* Confirmed summary */}
      {step === "confirmed" && summary && (
        <div
          aria-live="polite"
          className="mt-6 rounded-xl border border-border bg-card p-6 shadow-sm"
        >
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

          <button
            type="button"
            onClick={handleReset}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg border border-input bg-card px-4 py-2.5 font-medium text-secondary-foreground shadow-sm transition-colors hover:bg-muted"
          >
            <Plus className="size-4" />
            Upload Another
          </button>
        </div>
      )}
    </div>
  );
}
