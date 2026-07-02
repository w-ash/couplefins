import { useCallback } from "react";
import { useTemporary } from "@/hooks/useTemporary";

// Shared "Copied" feedback state for copy buttons. Clipboard writes stay in
// each consumer — payloads differ (plain text vs dual text/plain + text/html).
export function useCopyFeedback(ms = 1500) {
  const [copied, setCopied] = useTemporary(false, ms);
  const markCopied = useCallback(() => setCopied(true), [setCopied]);
  return { copied, markCopied };
}
