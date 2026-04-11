import { Loader2 } from "lucide-react";
import { lazy, Suspense, useCallback } from "react";
import { Outlet } from "react-router";
import { useHealthCheck } from "@/api/generated/health/health";
import { BottomNav } from "@/components/BottomNav";
import { ChatEdgeTab } from "@/components/chat/ChatEdgeTab";
import { Sidebar } from "@/components/Sidebar";

const ChatPanel = lazy(() =>
  import("@/components/chat/ChatPanel").then((m) => ({
    default: m.ChatPanel,
  })),
);

import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";
import { useRealtimeSync } from "@/hooks/useRealtimeSync";
import { useChatStore } from "@/lib/chat";

const DB_KEEPALIVE_MS = 4 * 60 * 1000;

export function AppLayout() {
  useRealtimeSync();
  const healthQuery = useHealthCheck({
    query: { refetchInterval: DB_KEEPALIVE_MS },
  });
  const health =
    healthQuery.data?.status === 200 ? healthQuery.data.data : undefined;
  const chatAvailable = health?.chat_available ?? false;

  const isPanelOpen = useChatStore((s) => s.isPanelOpen);

  const togglePanel = useCallback(() => {
    useChatStore.getState().togglePanel();
  }, []);

  useKeyboardShortcut(["cmd", "k"], togglePanel, chatAvailable);

  return (
    <div className="flex h-screen overflow-hidden">
      <a href="#main-content" className="skip-to-content">
        Skip to content
      </a>
      <div className="hidden md:flex">
        <Sidebar />
      </div>
      <main
        id="main-content"
        className="flex-1 overflow-y-auto bg-background pb-16 md:pb-0"
      >
        <Outlet />
      </main>
      {chatAvailable &&
        (isPanelOpen ? (
          <div className="hidden w-96 shrink-0 border-l border-border bg-card md:flex">
            <Suspense
              fallback={
                <div className="flex flex-1 items-center justify-center">
                  <Loader2 className="size-4 animate-spin text-muted-foreground" />
                </div>
              }
            >
              <ChatPanel />
            </Suspense>
          </div>
        ) : (
          <ChatEdgeTab />
        ))}
      <BottomNav chatAvailable={chatAvailable} />
    </div>
  );
}
