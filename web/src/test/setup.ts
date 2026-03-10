import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

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
