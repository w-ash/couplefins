import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { ThemeProvider } from "@/components/ThemeProvider";
import { useIdentityStore } from "@/lib/identity";
import { server } from "@/test/server";
import { App } from "./App";

const meResponse = {
  id: "p1",
  name: "Alice",
  adjustment_account: "adj-1",
  theme_preference: "system",
};

const authPersons = [
  { name: "Alice", has_password: true },
  { name: "Bob", has_password: true },
];

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

function mockAuth401() {
  return http.get("/api/v1/auth/me", () =>
    HttpResponse.json(
      { error: { code: "AUTHENTICATION_ERROR", message: "Not authenticated" } },
      { status: 401 },
    ),
  );
}

describe("App auth gate", () => {
  beforeEach(() => {
    useIdentityStore.setState({
      currentPersonId: null,
      currentPersonName: null,
    });
  });

  it("shows SetupPage when no persons exist", async () => {
    server.use(
      mockAuth401(),
      http.get("/api/v1/auth/persons", () => HttpResponse.json([])),
    );
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("Welcome to CoupleFins")).toBeInTheDocument();
    });
  });

  it("shows SetupPage when only one person exists", async () => {
    server.use(
      mockAuth401(),
      http.get("/api/v1/auth/persons", () =>
        HttpResponse.json([{ name: "Alice", has_password: true }]),
      ),
    );
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("Welcome to CoupleFins")).toBeInTheDocument();
    });
  });

  it("shows LoginPage when persons exist with passwords", async () => {
    server.use(
      mockAuth401(),
      http.get("/api/v1/auth/persons", () => HttpResponse.json(authPersons)),
    );
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("Welcome back")).toBeInTheDocument();
    });
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("shows SetInitialPasswordPage when persons have no passwords", async () => {
    server.use(
      mockAuth401(),
      http.get("/api/v1/auth/persons", () =>
        HttpResponse.json([
          { name: "Alice", has_password: false },
          { name: "Bob", has_password: false },
        ]),
      ),
    );
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("Set Your Password")).toBeInTheDocument();
    });
  });

  it("shows app shell when authenticated", async () => {
    server.use(
      http.get("/api/v1/auth/me", () => HttpResponse.json(meResponse)),
      http.get("/api/v1/dashboard", () => HttpResponse.json({})),
      http.get("/api/v1/persons/", () => HttpResponse.json([])),
    );
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("CoupleFins")).toBeInTheDocument();
    });
    expect(
      screen.getByRole("navigation", { name: "App navigation" }),
    ).toBeInTheDocument();
  });

  it("renders skip-to-content link in app shell", async () => {
    server.use(
      http.get("/api/v1/auth/me", () => HttpResponse.json(meResponse)),
      http.get("/api/v1/dashboard", () => HttpResponse.json({})),
      http.get("/api/v1/persons/", () => HttpResponse.json([])),
    );
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("Skip to content")).toBeInTheDocument();
    });
    const link = screen.getByText("Skip to content");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "#main-content");
  });

  it("shows error state when /auth/me returns non-401 error", async () => {
    server.use(
      http.get("/api/v1/auth/me", () =>
        HttpResponse.json(
          {
            error: {
              code: "INTERNAL_ERROR",
              message: "Database unavailable",
            },
          },
          { status: 500 },
        ),
      ),
    );
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("Database unavailable")).toBeInTheDocument();
    });
    expect(screen.getByText("Try Again")).toBeInTheDocument();
  });

  it("shows accessible loading state", () => {
    server.use(
      http.get("/api/v1/auth/me", async () => {
        await new Promise(() => {});
        return HttpResponse.json({});
      }),
    );
    renderApp();
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});
