import { Outlet } from "react-router";
import { BottomNav } from "@/components/BottomNav";
import { Sidebar } from "@/components/Sidebar";
import { useRealtimeSync } from "@/hooks/useRealtimeSync";

export function AppLayout() {
  useRealtimeSync();

  return (
    <div className="flex min-h-screen">
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
