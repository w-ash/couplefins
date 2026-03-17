import { Loader2 } from "lucide-react";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router";
import { useGetPersons } from "./api/generated/persons/persons";
import { Button } from "./components/Button";
import { AppLayout } from "./layouts/AppLayout";
import { useIdentityHydrated, useIdentityStore } from "./lib/identity";
import { BudgetPage } from "./pages/BudgetPage";
import { DashboardPage } from "./pages/DashboardPage";
import { InsightsPage } from "./pages/InsightsPage";
import { ProfilePicker } from "./pages/ProfilePicker";
import { SettingsPage } from "./pages/SettingsPage";
import { SettleUpPage } from "./pages/SettleUpPage";
import { SetupPage } from "./pages/SetupPage";
import { TransactionsPage } from "./pages/TransactionsPage";
import { UploadPage } from "./pages/UploadPage";

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "transactions", element: <TransactionsPage /> },
      { path: "settle", element: <SettleUpPage /> },
      { path: "budget", element: <BudgetPage /> },
      { path: "insights", element: <InsightsPage /> },
      { path: "upload", element: <UploadPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

export function App() {
  const {
    data: response,
    isLoading,
    isError,
    error,
    refetch,
  } = useGetPersons();
  const persons = response?.data;
  const currentPersonId = useIdentityStore((s) => s.currentPersonId);
  const hasHydrated = useIdentityHydrated();

  if (isLoading || !hasHydrated) {
    return (
      <output
        aria-label="Loading CoupleFins"
        className="flex min-h-screen items-center justify-center bg-background"
      >
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
        <span className="sr-only">Loading...</span>
      </output>
    );
  }

  if (isError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6">
        <p className="text-sm text-destructive-muted-foreground">
          {error instanceof Error
            ? error.message
            : "Could not connect to the server"}
        </p>
        <Button variant="secondary" size="sm" onClick={() => refetch()}>
          Try Again
        </Button>
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
