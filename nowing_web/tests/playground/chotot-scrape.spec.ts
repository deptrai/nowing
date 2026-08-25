import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * End-to-end smoke test for the Chợ Tốt multi-category scraper.
 *
 * This test exercises the real backend REST path against live chotot.com data.
 * It verifies the scrape endpoint returns typed car listings without a crash
 * and that cost_micros is computed from returned billable items.
 */

test.describe("Playwright Chotot multi-category scrape", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E Chotot ${Date.now()}`);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("should scrape real cars listings from chotot.com", async ({ request }) => {
		const response = await request.post(
			`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/workspaces/${workspaceId}/scrapers/chotot/scrape`,
			{
				headers: {
					Authorization: `Bearer ${ownerToken}`,
					"Content-Type": "application/json",
				},
				data: {
					category: "cars",
					city: "ho chi minh",
					listing_type: "buy",
					max_pages: 1,
					max_items: 2,
				},
			}
		);

		expect(
			response.ok(),
			`Expected 2xx, got ${response.status()}: ${await response.text()}`
		).toBeTruthy();

		const body = await response.json();
		expect(body).toHaveProperty("items");
		expect(Array.isArray(body.items)).toBe(true);
		expect(body.items.length).toBeGreaterThan(0);

		const first = body.items[0];
		expect(first).toHaveProperty("category", "cars");
		expect(first).toHaveProperty("title");
		expect(first).toHaveProperty("price_value");
		expect(first).toHaveProperty("detail_url");
		expect(first.detail_url).toMatch(/^https:\/\/xe\.chotot\.com\/\d+\.htm$/);
		expect(body).toHaveProperty("cost_micros");
		expect(body.cost_micros).toBeGreaterThan(0);
		expect(body).toHaveProperty("degraded", false);
	});
});
