import { Outlet } from "react-router";
import { useHealthCheck } from "@/api/generated/health/health";
import { BottomNav } from "@/components/BottomNav";
import { Sidebar } from "@/components/Sidebar";
import { useRealtimeSync } from "@/hooks/useRealtimeSync";

const DB_KEEPALIVE_MS = 4 * 60 * 1000;

export function AppLayout() {
  useRealtimeSync();
  // Keep Neon database connection warm while app is open
  useHealthCheck({ query: { refetchInterval: DB_KEEPALIVE_MS } });

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
      <BottomNav />
    </div>
  );
}
