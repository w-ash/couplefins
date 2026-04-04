import { useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import type { SettlementMerchantResponse } from "@/api/generated/model";
import {
  getGetSettlementMerchantsQueryKey,
  useDeleteSettlementMerchant,
  useGetSettlementMerchants,
  usePostSettlementMerchant,
} from "@/api/generated/settings/settings";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/InlineError";
import { PageError, PageLoading } from "@/components/PageStates";
import { baseInputClass } from "@/lib/input-styles";

function MerchantRow({
  merchant,
  onDelete,
  isDeleting,
}: {
  merchant: SettlementMerchantResponse;
  onDelete: () => void;
  isDeleting: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border-muted px-4 py-2.5">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-foreground">
          {merchant.name}
        </p>
        <p className="truncate font-mono text-xs text-muted-foreground">
          {merchant.merchant_pattern}
        </p>
      </div>
      <button
        type="button"
        onClick={onDelete}
        disabled={isDeleting}
        className="shrink-0 rounded-md p-2.5 sm:p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`Remove ${merchant.name}`}
      >
        {isDeleting ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Trash2 className="size-4" />
        )}
      </button>
    </div>
  );
}

function AddMerchantForm({ onSuccess }: { onSuccess: () => void }) {
  const [name, setName] = useState("");
  const [pattern, setPattern] = useState("");

  const mutation = usePostSettlementMerchant({
    mutation: {
      onSuccess: () => {
        setName("");
        setPattern("");
        onSuccess();
      },
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmedName = name.trim();
    const trimmedPattern = pattern.trim();
    if (trimmedName && trimmedPattern.length >= 2) {
      mutation.mutate({
        data: { name: trimmedName, merchant_pattern: trimmedPattern },
      });
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name (e.g. Venmo)"
          aria-label="Merchant name"
          className={`min-w-0 ${baseInputClass}`}
        />
        <input
          value={pattern}
          onChange={(e) => setPattern(e.target.value)}
          placeholder="Pattern (e.g. venmo)"
          aria-label="Merchant pattern"
          className={`min-w-0 font-mono ${baseInputClass}`}
        />
      </div>
      <p className="text-xs text-muted-foreground/70">
        The pattern matches against merchant names in your bank export.
        Case-insensitive.
      </p>
      <Button
        type="submit"
        size="sm"
        disabled={!name.trim() || pattern.trim().length < 2}
        loading={mutation.isPending}
        icon={<Plus className="size-4" />}
      >
        Add Merchant
      </Button>
      {mutation.isError && (
        <InlineError>
          {mutation.error instanceof Error
            ? mutation.error.message
            : "Failed to add merchant"}
        </InlineError>
      )}
    </form>
  );
}

export function SettlementMerchantsEditor() {
  const queryClient = useQueryClient();

  const {
    data: merchantsResponse,
    isLoading,
    isError,
    refetch,
  } = useGetSettlementMerchants();
  const merchants = merchantsResponse?.data ?? [];

  function invalidate() {
    queryClient.invalidateQueries({
      queryKey: getGetSettlementMerchantsQueryKey(),
    });
  }

  const [deletingId, setDeletingId] = useState<string | null>(null);

  const deleteMutation = useDeleteSettlementMerchant({
    mutation: {
      onSuccess: () => {
        setDeletingId(null);
        invalidate();
      },
    },
  });

  if (isLoading) {
    return <PageLoading label="Loading merchants..." />;
  }

  if (isError) {
    return (
      <PageError
        error={new Error("Failed to load settlement merchants.")}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-3">
      {merchants.length > 0 && (
        <div className="space-y-2">
          {merchants.map((m) => (
            <MerchantRow
              key={m.id}
              merchant={m}
              onDelete={() => {
                setDeletingId(m.id);
                deleteMutation.mutate({ merchantId: m.id });
              }}
              isDeleting={deletingId === m.id && deleteMutation.isPending}
            />
          ))}
        </div>
      )}

      {merchants.length === 0 && (
        <p className="py-2 text-sm text-muted-foreground">
          No settlement merchants configured yet. Add one below.
        </p>
      )}

      <AddMerchantForm onSuccess={invalidate} />
    </div>
  );
}
