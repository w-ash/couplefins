import { useEffect } from "react";
import { useNavigate } from "react-router";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { useIsMobile } from "@/hooks/useIsMobile";
import { useChatStore } from "@/lib/chat";

export function AskPage() {
  const isMobile = useIsMobile();
  const navigate = useNavigate();

  // On desktop, open the panel and go back instead of showing this page
  useEffect(() => {
    if (!isMobile) {
      useChatStore.getState().setPanelOpen(true);
      navigate("/", { replace: true });
    }
  }, [isMobile, navigate]);

  if (!isMobile) return null;

  return <ChatPanel fullScreen />;
}
