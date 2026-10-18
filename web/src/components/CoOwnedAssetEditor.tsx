import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { errorMessage } from "@/api/client";
import {
  useGetCoOwnedAsset,
  useSaveCoOwnedAsset,
} from "@/api/generated/house/house";
import type {
  ContributionKind,
  CoOwnedAssetResponse,
} from "@/api/generated/model";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/InlineError";
import { InlineSuccess } from "@/components/InlineSuccess";
import { PageError, PageLoading } from "@/components/PageStates";
import { HOUSE_QUERY_KEYS } from "@/hooks/useRealtimeSync";
import { cn } from "@/lib/cn";
import { CONTRIBUTION_KIND_LABELS } from "@/lib/house";
import { baseInputClass } from "@/lib/input-styles";

const ALL_KINDS = Object.keys(CONTRIBUTION_KIND_LABELS) as ContributionKind[];

function AssetForm({ asset }: { asset: CoOwnedAssetResponse | null }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(asset?.name ?? "");
  const [threshold, setThreshold] = useState(
    String(asset?.repair_threshold ?? 0),
  );
  const [kinds, setKinds] = useState<ContributionKind[]>(
    asset?.qualifying_kinds ?? ALL_KINDS,
  );
  const [balance, setBalance] = useState(
    asset?.bank_balance != null ? String(asset.bank_balance) : "",
  );
  const [balanceDate, setBalanceDate] = useState(
    asset?.bank_balance_as_of ?? "",
  );
  const [saved, setSaved] = useState(false);

  const mutation = useSaveCoOwnedAsset({
    mutation: {
      onSuccess: () => {
        setSaved(true);
        for (const queryKey of HOUSE_QUERY_KEYS) {
          queryClient.invalidateQueries({ queryKey });
        }
      },
    },
  });

  const thresholdValue = Number(threshold);
  const thresholdValid = threshold.trim() !== "" && thresholdValue >= 0;
  const balanceValid =
    balance.trim() === "" || Number.isFinite(Number(balance));
  const canSave = name.trim() !== "" && thresholdValid && balanceValid;

  function toggleKind(kind: ContributionKind) {
    setSaved(false);
    setKinds((prev) =>
      prev.includes(kind) ? prev.filter((k) => k !== kind) : [...prev, kind],
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSave) return;
    setSaved(false);
    const hasBalance = balance.trim() !== "";
    mutation.mutate({
      data: {
        name: name.trim(),
        repair_threshold: thresholdValue,
        qualifying_kinds: ALL_KINDS.filter((k) => kinds.includes(k)),
        bank_balance: hasBalance ? Number(balance) : null,
        bank_balance_as_of: hasBalance && balanceDate ? balanceDate : null,
      },
    });
  }

  const edit =
    (set: (v: string) => void) => (e: { target: { value: string } }) => {
      setSaved(false);
      set(e.target.value);
    };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {!asset && (
        <p className="text-sm text-muted-foreground">
          Set up the home once; both of you can edit it.
        </p>
      )}
      <label className="block space-y-1 text-sm font-medium text-foreground">
        Name
        <input
          value={name}
          onChange={edit(setName)}
          className={cn("w-full", baseInputClass)}
        />
      </label>
      <label className="block space-y-1 text-sm font-medium text-foreground">
        Repair threshold
        <input
          type="number"
          min={0}
          step="any"
          value={threshold}
          onChange={edit(setThreshold)}
          className={cn("w-full", baseInputClass)}
        />
      </label>
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-foreground">
          Qualifying contributions
        </legend>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {ALL_KINDS.map((kind) => (
            <label
              key={kind}
              className="flex items-center gap-2 text-sm text-foreground"
            >
              <input
                type="checkbox"
                checked={kinds.includes(kind)}
                onChange={() => toggleKind(kind)}
              />
              {CONTRIBUTION_KIND_LABELS[kind]}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="block space-y-1 text-sm font-medium text-foreground">
          Bank balance
          <input
            type="number"
            step="any"
            value={balance}
            onChange={edit(setBalance)}
            className={cn("w-full", baseInputClass)}
          />
        </label>
        <label className="block space-y-1 text-sm font-medium text-foreground">
          Bank balance date
          <input
            type="date"
            disabled={balance.trim() === ""}
            value={balanceDate}
            onChange={edit(setBalanceDate)}
            className={cn("w-full", baseInputClass)}
          />
          {balance.trim() === "" && (
            <span className="block text-xs font-normal text-muted-foreground">
              Enter a balance to set its date.
            </span>
          )}
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={!canSave} loading={mutation.isPending}>
          Save house
        </Button>
        {saved && <InlineSuccess>House saved</InlineSuccess>}
        {mutation.isError && (
          <InlineError>
            {errorMessage(mutation.error, "Failed to save the house")}
          </InlineError>
        )}
      </div>
    </form>
  );
}

export function CoOwnedAssetEditor() {
  const {
    data: res,
    error,
    isLoading,
    isError,
    refetch,
  } = useGetCoOwnedAsset();
  if (isLoading) return <PageLoading label="Loading the house..." />;
  if (isError || !res) {
    return (
      <PageError
        error={
          error instanceof Error && error.message
            ? error
            : new Error("Failed to load the house.")
        }
        onRetry={() => refetch()}
      />
    );
  }
  return <AssetForm key={res.data?.id ?? "new"} asset={res.data ?? null} />;
}
