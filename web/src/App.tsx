import { Loader2 } from "lucide-react";
import { useEffect } from "react";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router";
import { ApiError, setOnUnauthorized } from "./api/client";
import { useGetMe, useListAuthPersons } from "./api/generated/auth/auth";
import { Button } from "./components/Button";
import { useTheme } from "./components/ThemeProvider";
import { AppLayout } from "./layouts/AppLayout";
import { useIdentityStore } from "./lib/identity";
import { isValidTheme } from "./lib/theme";
import { AccountPage } from "./pages/AccountPage";
import { BudgetPage } from "./pages/BudgetPage";
import { DashboardPage } from "./pages/DashboardPage";
import { InsightsPage } from "./pages/InsightsPage";
import { LoginPage } from "./pages/LoginPage";
import { SetInitialPasswordPage } from "./pages/SetInitialPasswordPage";
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
      { path: "account", element: <AccountPage /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

function is401(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

function LoadingScreen() {
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

export function App() {
  const currentPersonId = useIdentityStore((s) => s.currentPersonId);
  const { setTheme, resetToSystem } = useTheme();

  // Primary: check if we're already authenticated
  const meQuery = useGetMe({ query: { retry: false } });

  // Secondary: only when not authenticated, determine which page to show
  const authPersonsQuery = useListAuthPersons({
    query: { enabled: meQuery.isError && is401(meQuery.error) },
  });

  // Populate identity + theme from /auth/me response
  useEffect(() => {
    if (meQuery.data?.data) {
      const person = meQuery.data.data;
      useIdentityStore.getState().setFromAuthResponse(person);
      const pref = person.theme_preference;
      if (isValidTheme(pref)) {
        setTheme(pref);
      }
    }
  }, [meQuery.data, setTheme]);

  // Wire up global 401 handler — clear identity + revert to system theme
  useEffect(() => {
    setOnUnauthorized(() => {
      useIdentityStore.getState().clearIdentity();
      resetToSystem();
      meQuery.refetch();
    });
  }, [meQuery.refetch, resetToSystem]);

  // Loading
  if (meQuery.isLoading) return <LoadingScreen />;

  // Authenticated
  if (meQuery.isSuccess && currentPersonId) {
    return <RouterProvider router={router} />;
  }

  // Not authenticated — determine sub-state
  if (meQuery.isError && is401(meQuery.error)) {
    if (authPersonsQuery.isLoading) return <LoadingScreen />;

    const persons = authPersonsQuery.data?.data ?? [];

    if (persons.length < 2) {
      return <SetupPage />;
    }

    if (persons.some((p) => !p.has_password)) {
      return (
        <SetInitialPasswordPage
          persons={persons}
          onSuccess={() => meQuery.refetch()}
        />
      );
    }

    return <LoginPage persons={persons} onSuccess={() => meQuery.refetch()} />;
  }

  // Non-401 error (network, 500, etc.)
  if (meQuery.isError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6">
        <p className="text-sm text-destructive-muted-foreground">
          {meQuery.error instanceof Error
            ? meQuery.error.message
            : "Could not connect to the server"}
        </p>
        <Button variant="secondary" size="sm" onClick={() => meQuery.refetch()}>
          Try Again
        </Button>
      </div>
    );
  }

  return <LoadingScreen />;
}
