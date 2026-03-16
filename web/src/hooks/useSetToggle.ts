import { useCallback, useState } from "react";

export function useSetToggle(initial?: Iterable<string>) {
  const [selected, setSelected] = useState<Set<string>>(() => new Set(initial));

  const toggle = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const setAll = useCallback((ids: Iterable<string>) => {
    setSelected(new Set(ids));
  }, []);

  const clear = useCallback(() => {
    setSelected(new Set());
  }, []);

  return { selected, toggle, setAll, clear } as const;
}
