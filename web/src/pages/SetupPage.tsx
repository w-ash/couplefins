import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Heart, Loader2, UserPlus } from "lucide-react";
import { type FormEvent, useState } from "react";

async function createPerson(name: string) {
  const res = await fetch("/api/v1/persons/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const body = await res.json();
    throw new Error(body?.detail ?? "Failed to create person");
  }
  return res.json();
}

export function SetupPage() {
  const queryClient = useQueryClient();
  const [name1, setName1] = useState("");
  const [name2, setName2] = useState("");

  const mutation = useMutation({
    mutationFn: async ({ name1, name2 }: { name1: string; name2: string }) => {
      await createPerson(name1.trim());
      await createPerson(name2.trim());
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["persons"] });
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name1.trim() || !name2.trim()) return;
    mutation.mutate({ name1, name2 });
  }

  const namesMatch =
    name1.trim() !== "" &&
    name1.trim().toLowerCase() === name2.trim().toLowerCase();

  return (
    <div className="min-h-screen bg-stone-50">
      <div className="mx-auto max-w-md px-6 py-24">
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex items-center justify-center rounded-full bg-teal-100 p-3">
            <Heart className="size-6 text-teal-600" />
          </div>
          <h1 className="font-semibold text-2xl text-stone-800">
            Welcome to Couplefins
          </h1>
          <p className="mt-2 text-sm text-stone-500">
            Enter both names to get started with shared finance tracking.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-5 rounded-xl border border-stone-200 bg-white p-6 shadow-sm"
        >
          <div>
            <label
              htmlFor="person1"
              className="mb-1.5 flex items-center gap-1.5 font-medium text-sm text-stone-700"
            >
              <UserPlus className="size-4" />
              Person 1
            </label>
            <input
              id="person1"
              type="text"
              value={name1}
              onChange={(e) => setName1(e.target.value)}
              placeholder="e.g. Alice"
              required
              disabled={mutation.isPending}
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-stone-800 shadow-sm placeholder:text-stone-400 focus:border-teal-500 focus:ring-1 focus:ring-teal-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          <div>
            <label
              htmlFor="person2"
              className="mb-1.5 flex items-center gap-1.5 font-medium text-sm text-stone-700"
            >
              <UserPlus className="size-4" />
              Person 2
            </label>
            <input
              id="person2"
              type="text"
              value={name2}
              onChange={(e) => setName2(e.target.value)}
              placeholder="e.g. Bob"
              required
              disabled={mutation.isPending}
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-stone-800 shadow-sm placeholder:text-stone-400 focus:border-teal-500 focus:ring-1 focus:ring-teal-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          {namesMatch && (
            <p className="text-sm text-amber-600">
              Both names are the same — are you sure?
            </p>
          )}

          {mutation.error && (
            <p className="text-sm text-red-600">{mutation.error.message}</p>
          )}

          <button
            type="submit"
            disabled={mutation.isPending || !name1.trim() || !name2.trim()}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-teal-600 px-4 py-2.5 font-medium text-white shadow-sm transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Setting up...
              </>
            ) : (
              "Get Started"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
