import { useCallback, useEffect, useState } from "react";

const DEFAULT_TIMEOUT_MS = 30_000;
const DEFAULT_SLOW_MS = 5_000;
const DEFAULT_SLOW_HINT =
  "Taking longer than usual \u2014 the database may need a moment to wake up";

interface MutationTimeoutResult {
  timedOut: boolean;
  slowHint: string | null;
  reset: () => void;
}

export function useMutationTimeout(
  isPending: boolean,
  {
    timeoutMs = DEFAULT_TIMEOUT_MS,
    slowMs = DEFAULT_SLOW_MS,
    slowHint = DEFAULT_SLOW_HINT,
  }: {
    timeoutMs?: number;
    slowMs?: number;
    slowHint?: string;
  } = {},
): MutationTimeoutResult {
  const [timedOut, setTimedOut] = useState(false);
  const [showSlowHint, setShowSlowHint] = useState(false);

  useEffect(() => {
    if (!isPending) {
      setShowSlowHint(false);
      setTimedOut(false);
      return;
    }

    const slowTimer = setTimeout(() => setShowSlowHint(true), slowMs);
    const timeoutTimer = setTimeout(() => setTimedOut(true), timeoutMs);

    return () => {
      clearTimeout(slowTimer);
      clearTimeout(timeoutTimer);
    };
  }, [isPending, slowMs, timeoutMs]);

  const reset = useCallback(() => {
    setTimedOut(false);
    setShowSlowHint(false);
  }, []);

  return {
    timedOut,
    slowHint: showSlowHint && !timedOut ? slowHint : null,
    reset,
  };
}
