import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

// Polyfill matchMedia for jsdom
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }),
});

// Polyfill localStorage for jsdom environments that lack it
if (
  typeof window.localStorage === "undefined" ||
  typeof window.localStorage.getItem !== "function"
) {
  const store = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, String(value)),
      removeItem: (key: string) => store.delete(key),
      clear: () => store.clear(),
      get length() {
        return store.size;
      },
      key: (index: number) => [...store.keys()][index] ?? null,
    },
    writable: true,
  });
}

// MSW server will be configured once Orval generates mock handlers
// For now, set up basic test lifecycle
beforeAll(() => {
  // server.listen({ onUnhandledRequest: "warn" });
});
afterEach(() => {
  // server.resetHandlers();
  cleanup();
});
afterAll(() => {
  // server.close();
});
