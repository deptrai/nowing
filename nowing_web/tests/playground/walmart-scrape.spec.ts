import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * End-to-end smoke tests for the Walmart scrape capability in the API Playground.
 */

test.describe("Playground Walmart scrape", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ page, request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E Walmart ${Date.now()}`);
		workspaceId = workspace.id;

		await page.route(
			/.*\/api\/v1\/workspaces\/\d+\/scrapers\/walmart\/scrape(\?.*)?$/,
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
								id: "walmart:553491704",
								title: "Ozark Trail 4-Person Dome Tent",
								price: 49.97,
								price_raw: "$49.97",
								currency: "USD",
								rating: 4.2,
								seller: "Walmart",
								availability: "IN_STOCK",
								product_url: "https://www.walmart.com/ip/Ozark-Trail-4-Person-Dome-Tent/553491704",
								image_url: "https://i5.walmartimages.com/ozark-tent.jpg",
								review_summary: [],
								source: "walmart",
								source_url: "https://www.walmart.com/ip/Ozark-Trail-4-Person-Dome-Tent/553491704",
								is_active: true,
							},
						],
						cost_micros: 5000,
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

	test("should render Walmart scrape in the playground catalog", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground`);

		const link = page.getByRole("link", { name: /walmart\.scrape/i });
		await expect(link).toBeVisible();
		await expect(link).toContainText("walmart.scrape");

		await link.click();
		await expect(page).toHaveURL(`/dashboard/${workspaceId}/playground/walmart/scrape`);
	});

	test("should load the runner page without a white-screen crash", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/walmart/scrape`);

		await expect(page.getByRole("heading", { name: "API Playground" })).toBeVisible();
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});

	test("should surface a scrape result without crashing", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/walmart/scrape`);

		// Expand the advanced inputs if they are collapsed.
		const advanced = page.getByRole("button", { name: /advanced/i });
		await advanced.click();

		const keywordInput = page.locator("#field-keyword");
		await keywordInput.fill("tent");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		await expect(page.getByText(/Ozark Trail|walmart/i).first()).toBeVisible();
	});
});
