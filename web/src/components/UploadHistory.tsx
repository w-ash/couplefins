import { ChevronDown, Clock } from "lucide-react";
import { useState } from "react";
import type { UploadHistoryEntryResponse } from "@/api/generated/model";
import { useGetUploadHistory } from "@/api/generated/uploads/uploads";
import { Card } from "@/components/Card";
import { PageError, PageLoading } from "@/components/PageStates";
import { PersonBadge } from "@/components/PersonBadge";
import { formatDateRange, formatRelativeTime, plural } from "@/lib/format";
import { getPersonAccentColor } from "@/types/person";

const INITIAL_LIMIT = 6;

function HistoryEntry({
  entry,
  personIndex,
}: {
  entry: UploadHistoryEntryResponse;
  personIndex: number;
}) {
  const dateRange = formatDateRange(
    entry.date_range_start,
    entry.date_range_end,
  );

  return (
    <div className="py-3">
      <div className="flex items-center gap-2">
        <PersonBadge
          name={entry.person_name}
          accentColor={getPersonAccentColor(personIndex)}
          size="xs"
        />
        <span className="min-w-0 truncate text-sm font-medium text-foreground">
          {entry.filename}
        </span>
        <span className="ml-auto shrink-0 text-xs text-muted-foreground">
          {formatRelativeTime(entry.uploaded_at)}
        </span>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
        <span className="tabular-nums">
          {plural("transaction", entry.transaction_count)}
        </span>
        {entry.shared_count > 0 && (
          <>
            <span aria-hidden>&middot;</span>
            <span className="tabular-nums">{entry.shared_count} shared</span>
          </>
        )}
        {dateRange && (
          <>
            <span aria-hidden>&middot;</span>
            <span className="tabular-nums">{dateRange}</span>
          </>
        )}
      </div>
    </div>
  );
}

export function UploadHistory() {
  const { data: response, isLoading, error, refetch } = useGetUploadHistory();
  const [expanded, setExpanded] = useState(false);

  if (isLoading) {
    return (
      <Card className="mt-8">
        <PageLoading label="Loading upload history..." />
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="mt-8">
        <PageError error={error} onRetry={refetch} />
      </Card>
    );
  }

  const entries = response?.status === 200 ? response.data.entries : [];

  if (entries.length === 0) {
    return (
      <div className="mt-8 text-center text-sm text-muted-foreground">
        <Clock className="mx-auto mb-1 size-5" />
        No uploads yet
      </div>
    );
  }

  // Build person index map from unique person_ids in order of appearance
  const personIndexMap = new Map<string, number>();
  for (const e of entries) {
    if (!personIndexMap.has(e.person_id)) {
      personIndexMap.set(e.person_id, personIndexMap.size);
    }
  }

  const visible = expanded ? entries : entries.slice(0, INITIAL_LIMIT);
  const remaining = entries.length - INITIAL_LIMIT;

  return (
    <Card as="section" className="mt-8">
      <h2 className="font-medium text-base text-foreground">Past Uploads</h2>

      <div className="mt-2 divide-y divide-border-muted">
        {visible.map((entry) => (
          <HistoryEntry
            key={entry.upload_id}
            entry={entry}
            personIndex={personIndexMap.get(entry.person_id) ?? 0}
          />
        ))}
      </div>

      {remaining > 0 && !expanded && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="mt-2 flex w-full items-center justify-center gap-1 rounded-lg py-2 text-sm text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
        >
          <ChevronDown className="size-4" />
          Show older uploads ({remaining} more)
        </button>
      )}
    </Card>
  );
}
