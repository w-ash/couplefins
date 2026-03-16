import { CheckCircle2, Clock } from "lucide-react";
import { getPersonAccentColor } from "@/types/person";

export function UploadStatusRow({
  statuses,
  personIndexMap,
}: {
  statuses: Array<{
    person_id: string;
    person_name: string;
    has_uploaded: boolean;
  }>;
  personIndexMap: Map<string, number>;
}) {
  return (
    <div className="flex items-center justify-center gap-6">
      {statuses.map((s) => {
        const color = getPersonAccentColor(
          personIndexMap.get(s.person_id) ?? -1,
        );
        return (
          <div key={s.person_id} className="flex items-center gap-2 text-sm">
            {s.has_uploaded ? (
              <CheckCircle2 className="size-4 text-positive" />
            ) : (
              <Clock className="size-4 text-muted-foreground" />
            )}
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}
            >
              {s.person_name}
            </span>
            <span
              className={
                s.has_uploaded ? "text-foreground" : "text-muted-foreground"
              }
            >
              {s.has_uploaded ? "uploaded" : "not yet"}
            </span>
          </div>
        );
      })}
    </div>
  );
}
