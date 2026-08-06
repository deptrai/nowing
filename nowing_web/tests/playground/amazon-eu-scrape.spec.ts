import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * End-to-end smoke tests for Amazon EU marketplaces in the API Playground.
 */

test.describe("Playground Amazon EU scrape", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ page, request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E Amazon EU ${Date.now()}`);
		workspaceId = workspace.id;

		await page.route(
			/.*\/api\/v1\/workspaces\/\d+\/scrapers\/amazon\/scrape(\?.*)?$/,
			async (route) => {
				const req = route.request();
				if (req.method() === "OPTIONS") {
					await route.fulfill({ status: 204 });
					return;
				}
				await route.fulfill({
					status: 200,
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						items: [
							{
								title: "Echo Dot (4th generation)",
								asin: "B08N5WRWNW",
								url: "https://www.amazon.de/dp/B08N5WRWNW",
								brand: "Amazon",
								price: { value: 49.99, currency: "EUR" },
								listPrice: { value: 59.99, currency: "EUR" },
								inStock: true,
								stars: 4.5,
								reviewsCount: 2500,
								thumbnailImage: "https://m.media-amazon.com/images/echo-dot.jpg",
							},
						],
						cost_micros: 3500,
						degraded: false,
						degradation_reason: null,
						total_items: 1,
					}),
				});
			}
		);
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("should render Amazon scrape in the playground catalog", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground`);

		const link = page.getByRole("link", { name: /amazon\.scrape/i });
		await expect(link).toBeVisible();
		await expect(link).toContainText("amazon.scrape");

		await link.click();
		await expect(page).toHaveURL(`/dashboard/${workspaceId}/playground/amazon/scrape`);
	});

	test("should load the runner page without a white-screen crash", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/amazon/scrape`);

		await expect(page.getByRole("heading", { name: "API Playground" })).toBeVisible();
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});

	test("should surface an EU scrape result without crashing", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/amazon/scrape`);

		// Expand the advanced inputs if they are collapsed.
		const advanced = page.getByRole("button", { name: /advanced/i });
		await advanced.click();

		// Select the Germany marketplace from the domain dropdown.
		await page.locator("#field-domain").click();
		await page.getByRole("option", { name: "Germany" }).click();

		const urlInput = page.locator("#field-urls");
		await urlInput.fill("https://www.amazon.de/dp/B08N5WRWNW");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		await expect(page.getByText(/EUR|amazon/i).first()).toBeVisible();
	});
});
