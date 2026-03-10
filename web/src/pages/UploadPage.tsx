import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useRef, useState } from "react";

interface Person {
  id: string;
  name: string;
  adjustment_account: string;
}

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

async function fetchPersons(): Promise<Person[]> {
  const res = await fetch("/api/v1/persons/");
  if (!res.ok) throw new Error("Failed to fetch persons");
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

export function UploadPage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [personId, setPersonId] = useState("");
  const [year, setYear] = useState(currentYear());
  const [month, setMonth] = useState(currentMonth());

  const personsQuery = useQuery({
    queryKey: ["persons"],
    queryFn: fetchPersons,
  });

  const uploadMutation = useMutation({
    mutationFn: uploadCsv,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["uploads"] });
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file || !personId) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("person_id", personId);
    formData.append("year", String(year));
    formData.append("month", String(month));
    uploadMutation.mutate(formData);
  }

  const summary = uploadMutation.data;

  return (
    <div className="min-h-screen bg-stone-50">
      <div className="mx-auto max-w-2xl px-6 py-12">
        <h1 className="mb-8 font-semibold text-2xl text-stone-800">
          Upload Transactions
        </h1>

        <form
          onSubmit={handleSubmit}
          className="space-y-6 rounded-xl border border-stone-200 bg-white p-6 shadow-sm"
        >
          {/* Person selector */}
          <div>
            <label
              htmlFor="person"
              className="mb-1.5 block font-medium text-sm text-stone-700"
            >
              Who are you?
            </label>
            <select
              id="person"
              value={personId}
              onChange={(e) => setPersonId(e.target.value)}
              required
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-stone-800 shadow-sm focus:border-teal-500 focus:ring-1 focus:ring-teal-500 focus:outline-none"
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
                className="mb-1.5 block font-medium text-sm text-stone-700"
              >
                Month
              </label>
              <select
                id="month"
                value={month}
                onChange={(e) => setMonth(Number(e.target.value))}
                className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-stone-800 shadow-sm focus:border-teal-500 focus:ring-1 focus:ring-teal-500 focus:outline-none"
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
                className="mb-1.5 block font-medium text-sm text-stone-700"
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
                className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-stone-800 shadow-sm focus:border-teal-500 focus:ring-1 focus:ring-teal-500 focus:outline-none"
              />
            </div>
          </div>

          {/* File input */}
          <div>
            <label
              htmlFor="csv-file"
              className="mb-1.5 block font-medium text-sm text-stone-700"
            >
              Monarch CSV
            </label>
            <input
              id="csv-file"
              ref={fileInputRef}
              type="file"
              accept=".csv"
              required
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-600 file:mr-3 file:rounded-md file:border-0 file:bg-teal-50 file:px-3 file:py-1 file:font-medium file:text-sm file:text-teal-700"
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={uploadMutation.isPending || !personId}
            className="w-full rounded-lg bg-teal-600 px-4 py-2.5 font-medium text-white shadow-sm transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {uploadMutation.isPending ? "Uploading..." : "Upload"}
          </button>
        </form>

        {/* Error */}
        {uploadMutation.isError && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {uploadMutation.error.message}
          </div>
        )}

        {/* Success summary */}
        {summary && (
          <div className="mt-6 rounded-xl border border-stone-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 font-medium text-lg text-stone-800">
              Upload Complete
            </h2>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <dt className="text-stone-500">Total transactions</dt>
              <dd className="font-medium text-stone-800 tabular-nums">
                {summary.total_transactions}
              </dd>
              <dt className="text-stone-500">Shared</dt>
              <dd className="font-medium text-teal-700 tabular-nums">
                {summary.shared_count}
              </dd>
              <dt className="text-stone-500">Personal</dt>
              <dd className="font-medium text-stone-600 tabular-nums">
                {summary.personal_count}
              </dd>
            </dl>

            {summary.unmapped_categories.length > 0 && (
              <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
                <p className="mb-1 font-medium text-sm text-amber-800">
                  Unmapped categories
                </p>
                <p className="text-sm text-amber-700">
                  {summary.unmapped_categories.join(", ")}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
