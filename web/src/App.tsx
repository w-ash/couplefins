import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router";
import { AppLayout } from "./layouts/AppLayout";
import { useIdentityHydrated, useIdentityStore } from "./lib/identity";
import { ProfilePicker } from "./pages/ProfilePicker";
import { SettingsPage } from "./pages/SettingsPage";
import { SetupPage } from "./pages/SetupPage";
import { UploadPage } from "./pages/UploadPage";
import { fetchPersons, PERSONS_QUERY_KEY } from "./types/person";

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/upload" replace /> },
      { path: "upload", element: <UploadPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "*", element: <Navigate to="/upload" replace /> },
    ],
  },
]);

export function App() {
  const { data: persons, isLoading } = useQuery({
    queryKey: PERSONS_QUERY_KEY,
    queryFn: fetchPersons,
  });
  const currentPersonId = useIdentityStore((s) => s.currentPersonId);
  const hasHydrated = useIdentityHydrated();

  if (isLoading || !hasHydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!persons || persons.length < 2) {
    return <SetupPage />;
  }

  const isValidIdentity = persons.some((p) => p.id === currentPersonId);
  if (!currentPersonId || !isValidIdentity) {
    return <ProfilePicker persons={persons} />;
  }

  return <RouterProvider router={router} />;
}
