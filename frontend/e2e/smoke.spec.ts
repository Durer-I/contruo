import { test, expect } from "@playwright/test";

/**
 * Minimal smoke test — extend in Sprint 15 with authenticated flows when
 * `PLAYWRIGHT_TEST_EMAIL` / password env vars and API seed are wired in CI.
 */
test.describe("public shell", () => {
  test("login page loads", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible({
      timeout: 15_000,
    });
  });
});
