import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
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
import { useIdentityStore } from "@/lib/identity";
import { fetchPersons, PERSONS_QUERY_KEY } from "@/types/person";

interface UploadSummary {
  upload_id: string;
  filename: string;
  period_year: number;
  period_month: number;
  total_transactions: number;
  shared_count: number;
  personal_count: number;
  unmapped_categories: string[];
}

interface PreviewTransaction {
  date: string;
  merchant: string;
  category: string;
  amount: number;
  is_shared: boolean;
  payer_percentage: number | null;
}

interface PreviewData {
  transactions: PreviewTransaction[];
  total_count: number;
  shared_count: number;
  personal_count: number;
  unmapped_categories: string[];
}

type Step = "form" | "preview" | "confirmed";
type Filter = "all" | "shared" | "personal";

async function previewCsv(formData: FormData): Promise<PreviewData> {
  const res = await fetch("/api/v1/uploads/preview", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json();
    throw new Error(body?.error?.message ?? "Preview failed");
  }
  return res.json();
}

async function uploadCsv(formData: FormData): Promise<UploadSummary> {
  const res = await fetch("/api/v1/uploads/", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json();
    throw new Error(body?.error?.message ?? "Upload failed");
  }
  return res.json();
}

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function currentYear() {
  return new Date().getFullYear();
}

function currentMonth() {
  return new Date().getMonth() + 1;
}

function formatDate(dateStr: string): string {
  const d = new Date(`${dateStr}T00:00:00`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(amount);
}

function formatSplit(tx: PreviewTransaction): string {
  if (!tx.is_shared) return "";
  const payer = tx.payer_percentage ?? 50;
  return `${payer} / ${100 - payer}`;
}

export function UploadPage() {
  const queryClient = useQueryClient();
  const currentPersonId = useIdentityStore((s) => s.currentPersonId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [personId, setPersonId] = useState(currentPersonId ?? "");
  useEffect(() => {
    if (currentPersonId) setPersonId(currentPersonId);
  }, [currentPersonId]);
  const [year, setYear] = useState(currentYear());
  const [month, setMonth] = useState(currentMonth());
  const [step, setStep] = useState<Step>("form");
  const [filter, setFilter] = useState<Filter>("all");

  const personsQuery = useQuery({
    queryKey: PERSONS_QUERY_KEY,
    queryFn: fetchPersons,
  });

  const previewMutation = useMutation({
    mutationFn: previewCsv,
    onSuccess: () => setStep("preview"),
  });

  const uploadMutation = useMutation({
    mutationFn: uploadCsv,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["uploads"] });
      setStep("confirmed");
    },
  });

  function handlePreview(e: FormEvent) {
    e.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file || !personId) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("person_id", personId);
    previewMutation.mutate(formData);
  }

  function handleConfirm() {
    const file = fileInputRef.current?.files?.[0];
    if (!file || !personId) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("person_id", personId);
    formData.append("year", String(year));
    formData.append("month", String(month));
    uploadMutation.mutate(formData);
  }

  function handleBack() {
    setStep("form");
    previewMutation.reset();
    setFilter("all");
  }

  function handleReset() {
    setStep("form");
    previewMutation.reset();
    uploadMutation.reset();
    setFilter("all");
    setPersonId("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  const isFormDisabled = step === "preview";
  const preview = previewMutation.data;
  const summary = uploadMutation.data;
  const error = previewMutation.error || uploadMutation.error;

  const filteredTransactions = preview?.transactions.filter((tx) => {
    if (filter === "shared") return tx.is_shared;
    if (filter === "personal") return !tx.is_shared;
    return true;
  });

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

        {/* Month/Year */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="month"
              className="mb-1.5 block font-medium text-sm text-secondary-foreground"
            >
              Month
            </label>
            <select
              id="month"
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              disabled={isFormDisabled}
              className="w-full rounded-lg border border-input bg-card px-3 py-2 text-foreground shadow-sm focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            >
              {MONTHS.map((name, i) => (
                <option key={name} value={i + 1}>
                  {name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label
              htmlFor="year"
              className="mb-1.5 block font-medium text-sm text-secondary-foreground"
            >
              Year
            </label>
            <input
              id="year"
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              min={2020}
              max={2030}
              disabled={isFormDisabled}
              className="w-full rounded-lg border border-input bg-card px-3 py-2 text-foreground shadow-sm focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>
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
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
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
      {error && (
        <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-destructive-border bg-destructive-muted p-4 text-sm text-destructive-muted-foreground">
          <CircleAlert className="mt-0.5 size-4 shrink-0" />
          {error.message}
        </div>
      )}

      {/* Preview */}
      {step === "preview" && preview && (
        <div className="mt-6 rounded-xl border border-border bg-card p-6 shadow-sm">
          <h2 className="mb-1 flex items-center gap-2 font-medium text-lg text-foreground">
            <Eye className="size-5" />
            Preview
          </h2>
          <p className="mb-4 text-sm text-muted-foreground">
            {preview.total_count} transactions ({preview.shared_count} shared,{" "}
            {preview.personal_count} personal)
          </p>

          {/* Unmapped categories warning */}
          {preview.unmapped_categories.length > 0 && (
            <div className="mb-4 rounded-lg border border-warning-border bg-warning-muted p-3">
              <p className="mb-1 flex items-center gap-1.5 font-medium text-sm text-warning">
                <AlertTriangle className="size-4 shrink-0" />
                Unmapped categories
              </p>
              <p className="text-sm text-warning-muted-foreground">
                {preview.unmapped_categories.join(", ")}
              </p>
            </div>
          )}

          {/* Filter pills */}
          <div className="mb-4 flex gap-2">
            {(["all", "shared", "personal"] as const).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFilter(f)}
                className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                  filter === f
                    ? "bg-primary-muted text-primary-muted-foreground"
                    : "bg-muted text-muted-foreground hover:bg-secondary"
                }`}
              >
                {f === "all"
                  ? `All (${preview.total_count})`
                  : f === "shared"
                    ? `Shared (${preview.shared_count})`
                    : `Personal (${preview.personal_count})`}
              </button>
            ))}
          </div>

          {/* Transaction table */}
          <div className="overflow-x-auto">
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
                {filteredTransactions?.map((tx) => (
                  <tr
                    key={`${tx.date}-${tx.merchant}-${tx.amount}-${tx.category}`}
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
                        formatSplit(tx)
                      ) : (
                        <Minus className="size-4 text-icon-muted" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Footer buttons */}
          <div className="mt-6 flex gap-3">
            <button
              type="button"
              onClick={handleConfirm}
              disabled={uploadMutation.isPending}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
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
        </div>
      )}

      {/* Confirmed summary */}
      {step === "confirmed" && summary && (
        <div className="mt-6 rounded-xl border border-border bg-card p-6 shadow-sm">
          <h2 className="mb-4 flex items-center gap-2 font-medium text-lg text-foreground">
            <Check className="size-5 text-primary" />
            Upload Complete
          </h2>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <dt className="text-muted-foreground">Total transactions</dt>
            <dd className="font-medium text-foreground tabular-nums">
              {summary.total_transactions}
            </dd>
            <dt className="text-muted-foreground">Shared</dt>
            <dd className="font-medium text-accent-foreground tabular-nums">
              {summary.shared_count}
            </dd>
            <dt className="text-muted-foreground">Personal</dt>
            <dd className="font-medium text-muted-foreground tabular-nums">
              {summary.personal_count}
            </dd>
          </dl>

          {summary.unmapped_categories.length > 0 && (
            <div className="mt-4 rounded-lg border border-warning-border bg-warning-muted p-3">
              <p className="mb-1 flex items-center gap-1.5 font-medium text-sm text-warning">
                <AlertTriangle className="size-4 shrink-0" />
                Unmapped categories
              </p>
              <p className="text-sm text-warning-muted-foreground">
                {summary.unmapped_categories.join(", ")}
              </p>
            </div>
          )}

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
