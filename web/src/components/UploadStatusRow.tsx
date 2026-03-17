import { CheckCircle2, Clock } from "lucide-react";
import { PersonBadge } from "@/components/PersonBadge";

export function UploadStatusRow({
  statuses,
  getPersonColor,
}: {
  statuses: Array<{
    person_id: string;
    person_name: string;
    has_uploaded: boolean;
  }>;
  getPersonColor: (id: string) => string;
}) {
  return (
    <div className="flex items-center justify-center gap-6">
      {statuses.map((s) => (
        <div key={s.person_id} className="flex items-center gap-2 text-sm">
          {s.has_uploaded ? (
            <CheckCircle2 className="size-4 text-positive" />
          ) : (
            <Clock className="size-4 text-muted-foreground" />
          )}
          <PersonBadge
            name={s.person_name}
            accentColor={getPersonColor(s.person_id)}
            size="xs"
          />
          <span
            className={
              s.has_uploaded ? "text-foreground" : "text-muted-foreground"
            }
          >
            {s.has_uploaded ? "uploaded" : "not yet"}
          </span>
        </div>
      ))}
    </div>
  );
}
