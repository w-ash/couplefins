import type { ActivityKind } from "@/api/generated/model";
import { Pill } from "@/components/Pill";
import { ACTIVITY_KIND_LABELS } from "@/lib/house";

/** Names what kind of movement an activity row is. */
export function ActivityKindPill({ kind }: { kind: ActivityKind }) {
  return <Pill>{ACTIVITY_KIND_LABELS[kind]}</Pill>;
}
