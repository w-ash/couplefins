import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      // Vitest 4: top-level (poolOptions was removed in v4). Disables Node 25's
      // native Web Storage so jsdom's localStorage serves tests, silencing the
      // "--localstorage-file was provided without a valid path" warning MSW's
      // cookieStore triggers by probing global localStorage at import.
      execArgv: ["--no-experimental-webstorage"],
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      exclude: ["src/api/generated/**"],
    },
  }),
);
