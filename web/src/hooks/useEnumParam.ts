import { useCallback } from "react";
import { useSearchParams } from "react-router";

/**
 * Read and write a single URL search param validated against a fixed set of values.
 * Deletes the param when the value matches the default (keeps URLs clean).
 */
export function useEnumParam<T extends string>(
  key: string,
  validValues: Set<T>,
  defaultValue: T,
): [value: T, setValue: (v: T) => void] {
  const [searchParams, setSearchParams] = useSearchParams();

  const raw = searchParams.get(key);
  const value: T =
    raw != null && validValues.has(raw as T) ? (raw as T) : defaultValue;

  const setValue = useCallback(
    (v: T) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (v === defaultValue) next.delete(key);
          else next.set(key, v);
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams, key, defaultValue],
  );

  return [value, setValue];
}
