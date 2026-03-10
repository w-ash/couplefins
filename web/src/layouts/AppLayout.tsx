import { Outlet } from "react-router";
import { Sidebar } from "@/components/Sidebar";

export function AppLayout() {
  return (
    <div className="flex min-h-screen">
      <a href="#main-content" className="skip-to-content">
        Skip to content
      </a>
      <Sidebar />
      <main id="main-content" className="flex-1 overflow-y-auto bg-background">
        <Outlet />
      </main>
    </div>
  );
}
