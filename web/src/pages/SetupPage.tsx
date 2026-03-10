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
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-md px-6 py-24">
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex items-center justify-center rounded-full bg-primary-muted p-3">
            <Heart className="size-6 text-primary" />
          </div>
          <h1 className="font-semibold text-2xl text-foreground">
            Welcome to Couplefins
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Enter both names to get started with shared finance tracking.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-5 rounded-xl border border-border bg-card p-6 shadow-sm"
        >
          <div>
            <label
              htmlFor="person1"
              className="mb-1.5 flex items-center gap-1.5 font-medium text-sm text-secondary-foreground"
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
              className="w-full rounded-lg border border-input bg-card px-3 py-2 text-foreground shadow-sm placeholder:text-placeholder focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          <div>
            <label
              htmlFor="person2"
              className="mb-1.5 flex items-center gap-1.5 font-medium text-sm text-secondary-foreground"
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
              className="w-full rounded-lg border border-input bg-card px-3 py-2 text-foreground shadow-sm placeholder:text-placeholder focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          {namesMatch && (
            <p className="text-sm text-warning">
              Both names are the same — are you sure?
            </p>
          )}

          {mutation.error && (
            <p className="text-sm text-destructive">{mutation.error.message}</p>
          )}

          <button
            type="submit"
            disabled={mutation.isPending || !name1.trim() || !name2.trim()}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
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
