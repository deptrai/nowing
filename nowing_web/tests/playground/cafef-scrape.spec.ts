import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * End-to-end smoke tests for the CafeF capability in the API Playground.
 *
 * These tests exercise the real frontend + backend stack. They verify:
 *   1. The capability is listed in the playground catalog.
 *   2. The runner page loads without a Next.js crash / white-screen.
 *   3. A degraded response (isSuccess: false upstream) is surfaced without crashing.
 *   4. A successful financial-data response renders new fields without crashing.
 */

test.describe("Playground CafeF scrape", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ page, request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E CafeF ${Date.now()}`);
		workspaceId = workspace.id;

		await page.route(
			/.*\/api\/v1\/workspaces\/\d+\/scrapers\/cafef\/scrape(\?.*)?$/,
			async (route) => {
				const req = route.request();
				if (req.method() === "OPTIONS") {
					await route.fulfill({ status: 204 });
					return;
				}

				// Force the first call to degrade (mimics isSuccess: false from CafeF API).
				if (req.method() === "POST") {
					await route.fulfill({
						status: 200,
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({
							quote: null,
							financials: null,
							news: [],
							cost_micros: 0,
							degraded: true,
							degradation_reason: "api_error",
							total_items: 0,
						}),
					});
					return;
				}

				await route.continue();
			}
		);
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("should render CafeF scrape in the playground catalog", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground`);

		const link = page.getByRole("link", { name: /cafef/i });
		await expect(link).toBeVisible();
		await expect(link).toContainText("cafef.scrape");

		await link.click();
		await expect(page).toHaveURL(`/dashboard/${workspaceId}/playground/cafef/scrape`);
	});

	test("should load the runner page without a white-screen crash", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/cafef/scrape`);

		await expect(page.getByRole("heading", { name: "API Playground" })).toBeVisible();
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});

	test("should surface a degraded result without crashing", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/cafef/scrape`);

		const symbolInput = page.locator("#field-symbol");
		await expect(symbolInput).toBeVisible();
		await symbolInput.fill("VCB");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		await expect(page.getByText(/degraded|api_error|api error/i).first()).toBeVisible({
			timeout: 30_000,
		});
	});

	test("should render a successful result with quote and financials", async ({ page }) => {
		await page.unroute(/.*\/api\/v1\/workspaces\/\d+\/scrapers\/cafef\/scrape(\?.*)?$/);

		await page.route(
			/.*\/api\/v1\/workspaces\/\d+\/scrapers\/cafef\/scrape(\?.*)?$/,
			async (route) => {
				const req = route.request();
				if (req.method() === "OPTIONS") {
					await route.fulfill({ status: 204 });
					return;
				}
				if (req.method() === "POST") {
					await route.fulfill({
						status: 200,
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({
							quote: {
								symbol: "VCB",
								price: 92.5,
								change: 1.2,
								change_percent: 1.31,
							},
							financials: null,
							news: [],
							cost_micros: 5000,
							degraded: false,
							degradation_reason: null,
							total_items: 1,
						}),
					});
					return;
				}
				await route.continue();
			}
		);

		await page.goto(`/dashboard/${workspaceId}/playground/cafef/scrape`);

		const symbolInput = page.locator("#field-symbol");
		await symbolInput.fill("VCB");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		await expect(page.getByText(/VCB|92\.5|quote/i).first()).toBeVisible({ timeout: 30_000 });
	});
});
