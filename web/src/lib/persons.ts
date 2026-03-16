import { useMemo } from "react";

export function usePersonMaps(
  persons: Array<{ id: string; name: string }> | undefined,
) {
  return useMemo(() => {
    const list = persons ?? [];
    return {
      personNames: new Map(list.map((p) => [p.id, p.name])),
      personIndexMap: new Map(list.map((p, i) => [p.id, i])),
    };
  }, [persons]);
}
