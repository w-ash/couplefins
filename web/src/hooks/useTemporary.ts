import { useEffect, useRef, useState } from "react";

export function useTemporary<T>(
  initial: T,
  ms = 2000,
  onExpire?: () => void,
): [T, (value: T) => void] {
  const [value, setValue] = useState(initial);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  useEffect(() => {
    if (value === initial) return;
    const id = setTimeout(() => {
      onExpireRef.current?.();
      setValue(initial);
    }, ms);
    return () => clearTimeout(id);
  }, [value, initial, ms]);

  return [value, setValue];
}
