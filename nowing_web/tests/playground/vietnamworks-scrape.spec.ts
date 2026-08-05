import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * End-to-end smoke tests for the VietnamWorks capability in the API Playground.
 *
 * These tests exercise the real frontend + backend stack. They verify:
 *   1. The capability is listed in the playground catalog.
 *   2. The runner page loads without a Next.js crash / white-screen.
 *   3. A schema-drift / upstream error is surfaced to the user instead of crashing.
 *
 * Full run-through tests that mock the scraper API response are left as an
 * exercise for a same-origin or Caddy-backed test environment, because
 * Playwright `page.route` cannot reliably intercept cross-origin `fetch`
 * requests made from the Next.js dev server in this local setup.
 */

test.describe("Playground VietnamWorks scrape", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ page, request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E VietnamWorks ${Date.now()}`);
		workspaceId = workspace.id;

		// Block the scraper run endpoint so the tests never accidentally trigger a
		// real live call to VietnamWorks if the runner form loads.
		await page.route(
			/.*\/api\/v1\/workspaces\/\d+\/scrapers\/vietnamworks\/scrape(\?.*)?$/,
			async (route) => {
				const req = route.request();
				if (req.method() === "OPTIONS") {
					await route.fulfill({ status: 204 });
					return;
				}
				await route.fulfill({
					status: 502,
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						error: {
							code: "CAPABILITY_UPSTREAM_ERROR",
							message: "VietnamWorks response schema drift: missing jobId in job entry",
							status: 502,
							request_id: "req-001",
							timestamp: new Date().toISOString(),
							report_url: null,
						},
					}),
				});
			}
		);
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("should render VietnamWorks scrape in the playground catalog", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground`);

		const link = page.getByRole("link", { name: /vietnamworks/i });
		await expect(link).toBeVisible();
		await expect(link).toContainText("vietnamworks.scrape");

		await link.click();
		await expect(page).toHaveURL(`/dashboard/${workspaceId}/playground/vietnamworks/scrape`);
	});

	test("should load the runner page without a white-screen crash", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/vietnamworks/scrape`);

		// Page loads and the playground shell is rendered.
		await expect(page.getByRole("heading", { name: "API Playground" })).toBeVisible();

		// No Next.js error overlay.
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});

	test("should surface an upstream error without crashing", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/vietnamworks/scrape`);

		// If the runner form loaded, attempt to run and assert an error toast
		// (not a white-screen) is shown. If the capability endpoint is not
		// reachable in this environment, the page still must not crash.
		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		await expect(page.getByText(/schema drift|upstream|error/i).first()).toBeVisible();
	});
});
