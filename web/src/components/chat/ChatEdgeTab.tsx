import { MessageCircle } from "lucide-react";
import { useChatStore } from "@/lib/chat";

export function ChatEdgeTab() {
  const togglePanel = useChatStore((s) => s.togglePanel);

  return (
    <button
      type="button"
      onClick={togglePanel}
      className="hidden w-10 shrink-0 cursor-pointer items-center justify-center border-l border-border bg-card transition-colors hover:bg-muted md:flex"
      aria-label="Open chat assistant"
    >
      <MessageCircle className="size-[18px] text-muted-foreground" />
    </button>
  );
}
