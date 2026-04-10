import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import { useEffect } from "react";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router";
import { ApiError, setOnUnauthorized } from "./api/client";
import { useGetMe, useListAuthPersons } from "./api/generated/auth/auth";
import { useHealthCheck } from "./api/generated/health/health";
import { Button } from "./components/Button";
import { useTheme } from "./components/ThemeProvider";
import { AppLayout } from "./layouts/AppLayout";
import { useIdentityStore } from "./lib/identity";
import { isValidTheme } from "./lib/theme";
import { AccountPage } from "./pages/AccountPage";
import { AskPage } from "./pages/AskPage";
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
      { path: "ask", element: <AskPage /> },
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

function ErrorScreen({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry: () => void;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6">
      <p className="text-sm text-destructive-muted-foreground">
        {error instanceof Error
          ? error.message
          : "Could not connect to the server"}
      </p>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        Try Again
      </Button>
    </div>
  );
}

function UpgradeScreen({
  schemaVersion,
  schemaCurrent,
  onRetry,
}: {
  schemaVersion: string;
  schemaCurrent: string;
  onRetry: () => void;
}) {
  const codeBehind = schemaCurrent > schemaVersion;

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-md px-6 py-24">
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex items-center justify-center rounded-full bg-warning-muted p-3">
            <AlertTriangle className="size-6 text-warning" />
          </div>
          <h1 className="font-semibold text-2xl text-foreground">
            Update Required
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {codeBehind
              ? "Couplefins has been updated. Pull the latest code and restart your dev server."
              : "The database needs migration. Restart your dev server to apply it."}
          </p>
        </div>

        <div className="rounded-lg border border-border bg-surface p-4">
          <p className="mb-3 text-xs font-medium text-muted-foreground">
            Run in your terminal:
          </p>
          <pre className="rounded-md bg-background p-3 font-mono text-sm text-foreground">
            {codeBehind ? "git pull origin main && make dev" : "make dev"}
          </pre>
        </div>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          Expected schema {schemaVersion}, database has {schemaCurrent}
        </p>

        <div className="mt-6 text-center">
          <Button variant="secondary" size="sm" onClick={onRetry}>
            <RefreshCw className="mr-1.5 size-3.5" />
            Check Again
          </Button>
        </div>
      </div>
    </div>
  );
}

export function App() {
  const currentPersonId = useIdentityStore((s) => s.currentPersonId);
  const { setTheme, resetToSystem } = useTheme();

  const healthQuery = useHealthCheck({ query: { retry: false } });
  const health =
    healthQuery.data?.status === 200 ? healthQuery.data.data : undefined;
  const schemaOk = health?.schema_ok ?? false;

  const meQuery = useGetMe({ query: { retry: false, enabled: schemaOk } });

  const authPersonsQuery = useListAuthPersons({
    query: { enabled: schemaOk && meQuery.isError && is401(meQuery.error) },
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

  if (healthQuery.isLoading) return <LoadingScreen />;

  if (healthQuery.isError) {
    return (
      <ErrorScreen
        error={healthQuery.error}
        onRetry={() => healthQuery.refetch()}
      />
    );
  }

  if (health && !schemaOk) {
    return (
      <UpgradeScreen
        schemaVersion={health.schema_version}
        schemaCurrent={health.schema_current}
        onRetry={() => healthQuery.refetch()}
      />
    );
  }

  if (meQuery.isLoading) return <LoadingScreen />;

  if (meQuery.isSuccess && currentPersonId) {
    return <RouterProvider router={router} />;
  }

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

  if (meQuery.isError) {
    return (
      <ErrorScreen error={meQuery.error} onRetry={() => meQuery.refetch()} />
    );
  }

  return <LoadingScreen />;
}
