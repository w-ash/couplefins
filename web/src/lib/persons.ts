import { useMemo } from "react";
import { getPersonAccentColor } from "@/types/person";

export function usePersonMaps(
  persons: Array<{ id: string; name: string }> | undefined,
) {
  return useMemo(() => {
    const list = persons ?? [];
    const personNames = new Map(list.map((p) => [p.id, p.name]));
    const personIndexMap = new Map(list.map((p, i) => [p.id, i]));
    return {
      personNames,
      personIndexMap,
      getPersonName: (id: string) => personNames.get(id) ?? "Unknown",
      getPersonColor: (id: string) =>
        getPersonAccentColor(personIndexMap.get(id) ?? -1),
    };
  }, [persons]);
}
