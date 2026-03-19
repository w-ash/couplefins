import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { ThemeProvider } from "@/components/ThemeProvider";
import { useIdentityStore } from "@/lib/identity";
import { server } from "@/test/server";
import { App } from "./App";

const persons = [
  { id: "p1", name: "Alice", adjustment_account: "adj-1" },
  { id: "p2", name: "Bob", adjustment_account: "adj-2" },
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

describe("App three-state gate", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: null });
  });

  it("shows SetupPage when no persons exist", async () => {
    server.use(http.get("/api/v1/persons/", () => HttpResponse.json([])));
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("Welcome to CoupleFins")).toBeInTheDocument();
    });
  });

  it("shows SetupPage when only one person exists", async () => {
    server.use(
      http.get("/api/v1/persons/", () => HttpResponse.json([persons[0]])),
    );
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("Welcome to CoupleFins")).toBeInTheDocument();
    });
  });

  it("shows ProfilePicker when persons exist but no identity is stored", async () => {
    server.use(http.get("/api/v1/persons/", () => HttpResponse.json(persons)));
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("Who are you?")).toBeInTheDocument();
    });
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("shows ProfilePicker when stored identity is stale", async () => {
    useIdentityStore.setState({ currentPersonId: "nonexistent-id" });
    server.use(http.get("/api/v1/persons/", () => HttpResponse.json(persons)));
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("Who are you?")).toBeInTheDocument();
    });
  });

  it("shows app shell when identity is valid", async () => {
    useIdentityStore.setState({ currentPersonId: "p1" });
    server.use(
      http.get("/api/v1/persons/", () => HttpResponse.json(persons)),
      http.get("/api/v1/dashboard", () => HttpResponse.json({})),
    );
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("CoupleFins")).toBeInTheDocument();
    });
    expect(
      screen.getByRole("navigation", { name: "App navigation" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "Mobile navigation" }),
    ).toBeInTheDocument();
  });

  it("renders skip-to-content link in app shell", async () => {
    useIdentityStore.setState({ currentPersonId: "p1" });
    server.use(
      http.get("/api/v1/persons/", () => HttpResponse.json(persons)),
      http.get("/api/v1/dashboard", () => HttpResponse.json({})),
    );
    renderApp();
    await waitFor(() => {
      expect(screen.getByText("Skip to content")).toBeInTheDocument();
    });
    const link = screen.getByText("Skip to content");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "#main-content");
  });

  it("shows error state when persons API fails", async () => {
    server.use(
      http.get("/api/v1/persons/", () =>
        HttpResponse.json(
          {
            error: { code: "INTERNAL_ERROR", message: "Database unavailable" },
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
      http.get("/api/v1/persons/", async () => {
        await new Promise(() => {});
        return HttpResponse.json([]);
      }),
    );
    renderApp();
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});
