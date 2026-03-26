/**
 * Screenshot capture script for visual UI review.
 *
 * Usage:
 *   1. Start the dev server:  pnpm start
 *   2. Run screenshots:       pnpm screenshots
 *   3. Review:                 open screenshots/
 *
 * Captures every route in light + dark mode, desktop + mobile viewports.
 * No assertions — this is a visual review tool, not a test suite.
 */
import { test, type Page } from "@playwright/test";
import { existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const SCREENSHOT_DIR = join(import.meta.dirname, "..", "screenshots");

const ROUTES = [
  { path: "/", name: "dashboard" },
  { path: "/transactions", name: "transactions" },
  { path: "/settle-up", name: "settle-up" },
  { path: "/budget", name: "budget" },
  { path: "/insights", name: "insights" },
  { path: "/upload", name: "upload" },
  { path: "/settings", name: "settings" },
];

const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844 },
];

const THEMES = ["light", "dark"] as const;

async function login(page: Page) {
  // Try to log in — if the app redirects to login, fill in credentials.
  // Uses the first person name found on the login page.
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  // Check if we're on a login/setup page
  const url = page.url();
  if (url.includes("/login") || url.includes("/setup")) {
    // On login page: click the first person card and enter password
    const personCard = page.locator("button").filter({ hasText: /.+/ }).first();
    if (await personCard.isVisible()) {
      await personCard.click();
      await page.waitForTimeout(300);

      // Fill password if there's a password field
      const passwordInput = page.locator('input[type="password"]');
      if (await passwordInput.isVisible()) {
        await passwordInput.fill("password");
        await page.locator('button[type="submit"]').click();
        await page.waitForLoadState("networkidle");
      }
    }
  }
}

test("capture all pages", async ({ page }) => {
  if (!existsSync(SCREENSHOT_DIR)) {
    mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  // Log in once
  await login(page);

  for (const theme of THEMES) {
    // Emulate color scheme
    await page.emulateMedia({ colorScheme: theme });

    for (const viewport of VIEWPORTS) {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });

      for (const route of ROUTES) {
        await page.goto(route.path);
        await page.waitForLoadState("networkidle");
        // Extra settle time for animations
        await page.waitForTimeout(500);

        const filename = `${route.name}-${theme}-${viewport.name}.png`;
        await page.screenshot({
          path: join(SCREENSHOT_DIR, filename),
          fullPage: true,
        });
      }
    }
  }
});
