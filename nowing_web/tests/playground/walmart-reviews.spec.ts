import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * End-to-end smoke tests for the Walmart reviews capability in the API Playground.
 */

test.describe("Playground Walmart reviews", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ page, request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`E2E Walmart Reviews ${Date.now()}`
		);
		workspaceId = workspace.id;

		await page.route(
			/.*\/api\/v1\/workspaces\/\d+\/scrapers\/walmart\/reviews(\?.*)?$/,
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
								text: "Great tent for the price. Easy setup.",
								rating: 5,
								date: "2026-07-15T10:00:00Z",
								verified: true,
							},
							{
								text: "A bit snug for four adults but works well.",
								rating: 4,
								date: "2026-07-10T10:00:00Z",
								verified: false,
							},
						],
						cost_micros: 1000,
						degraded: false,
						degradation_reason: null,
						total_items: 2,
					}),
				});
			}
		);
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("should render Walmart reviews in the playground catalog", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground`);

		const reviewsLink = page.getByRole("link", { name: /walmart\.reviews/i });
		await expect(reviewsLink).toBeVisible();
		await expect(reviewsLink).toContainText("walmart.reviews");

		await reviewsLink.click();
		await expect(page).toHaveURL(`/dashboard/${workspaceId}/playground/walmart/reviews`);
	});

	test("should load the runner page without a white-screen crash", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/walmart/reviews`);

		await expect(page.getByRole("heading", { name: "API Playground" })).toBeVisible();
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});

	test("should surface a reviews result without crashing", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/walmart/reviews`);

		const urlInput = page.locator("#field-url");
		await urlInput.fill("https://www.walmart.com/ip/Ozark-Trail-4-Person-Dome-Tent/553491704");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		await expect(page.getByText(/Great tent|snug|verified/i).first()).toBeVisible();
	});
});
