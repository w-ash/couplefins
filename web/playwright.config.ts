import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: "http://localhost:5174",
  },
  projects: [
    {
      name: "screenshots",
      use: {
        browserName: "chromium",
      },
    },
  ],
  // Expect the dev server to already be running
  webServer: undefined,
});
