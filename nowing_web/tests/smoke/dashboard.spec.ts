import { expect, test } from "../fixtures";

/**
 * Tracer-bullet smoke test: proves the entire E2E pipeline is wired up.
 *
 * Verifies:
 *   - Web server is reachable
 *   - tests/auth.setup.ts ran and stored a valid bearer token
 *   - Dashboard route renders for an authenticated user
 *
 * Keep minimal. Connector- or feature-specific behaviour belongs under
 * tests/connectors/ or tests/<feature>/.
 */
test.describe("Smoke", () => {
	// The seeded auth state may inherit a Vietnamese locale (nowing-locale /
	// NEXT_LOCALE from the host). Pin English so assertions stay semantic.
	test.use({ locale: "en-US", timezoneId: "America/New_York" });

	test.beforeEach(async ({ page }) => {
		await page.addInitScript(() => {
			localStorage.setItem("nowing-locale", "en");
		});
	});

	test("dashboard loads for authenticated user", async ({ page }) => {
		await page.goto("/dashboard");

		// Sidebar / dashboard content visibility implies redirect + auth fetch.
		// "New chat" renders as a sidebar <a> link (not a button).
		await expect(page.getByRole("link", { name: /new chat/i }).first()).toBeVisible({
			timeout: 60_000,
		});
	});
});
