import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * Red-phase E2E tests for Story 21.7: Outcome-Based Pricing & Transparent Credit Ledger.
 *
 * Asserts the expected UI behavior for:
 * 1. Service breakdown donut and bar charts
 * 2. Interactive promo code claim card with balance update
 * 3. Outcome ROI metric cards (Meetings Booked, Cost/Meeting, ROI)
 */

test.describe("Story 21.7: Outcome Pricing & Transparent Ledger", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `ATDD Story 21.7 ${Date.now()}`);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test.skip("usage page renders 5 service categories in breakdown", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/usage`);

		// Assert 5 service category labels exist
		await expect(page.getByText(/AI Generation/i)).toBeVisible();
		await expect(page.getByText(/Web Search/i)).toBeVisible();
		await expect(page.getByText(/Social Media/i)).toBeVisible();
		await expect(page.getByText(/Phone Waterfall/i)).toBeVisible();
		await expect(page.getByText(/Outcome Meetings/i)).toBeVisible();
	});

	test.skip("user can claim promo code and see updated wallet balance", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/usage`);

		// Find Promo code input
		const promoInput = page.getByPlaceholder(/nhập mã|enter promo/i);
		await expect(promoInput).toBeVisible();

		await promoInput.fill("WELCOME50");
		const claimButton = page.getByRole("button", { name: /nhận|claim/i });
		await claimButton.click();

		// Toast notification for successful claim
		await expect(page.getByText(/thành công|claimed successfully/i)).toBeVisible();
	});

	test.skip("usage page renders outcome ROI metric summary cards", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/usage`);

		// Assert Outcome ROI metrics
		await expect(page.getByText(/meetings booked|cuộc hẹn/i)).toBeVisible();
		await expect(page.getByText(/cost per meeting|chi phí \/ cuộc hẹn/i)).toBeVisible();
		await expect(page.getByText(/estimated roi|hiệu quả roi/i)).toBeVisible();
	});
});
