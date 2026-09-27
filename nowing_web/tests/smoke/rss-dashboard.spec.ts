import { expect, test } from "../fixtures";

/**
 * Story 14.1: RSS Feed Integration — Playwright MCP smoke test.
 *
 * Verifies the dashboard connectors route still renders after the RSS feed
 * connector type was added to the backend enums and connector catalog.
 */
test.describe("Smoke", () => {
	// Pin English: seeded state may carry nowing-locale=vi from the host
	// timezone, which renders "Integration đã kết nối" instead of the English
	// "Connected integrations" this test asserts on.
	test.use({ locale: "en-US", timezoneId: "America/New_York" });

	test.beforeEach(async ({ page }) => {
		await page.addInitScript(() => {
			localStorage.setItem("nowing-locale", "en");
		});
	});

	test("RSS connector catalog renders on connectors page", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/connectors`);

		// The connectors page should render the catalog header and search input.
		await expect(page.getByText("Connected integrations").first()).toBeVisible({
			timeout: 30_000,
		});
		await expect(page.getByPlaceholder("Search integrations…")).toBeVisible();

		// RSS should appear as an available native connector.
		await expect(page.getByText("RSS").first()).toBeVisible();
	});
});
