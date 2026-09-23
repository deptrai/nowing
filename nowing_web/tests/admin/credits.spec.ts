import type { Page, Route } from "@playwright/test";
import { expect, test } from "../fixtures";
import { mockAdminAuth } from "../helpers/admin-auth";
import { fulfillJson } from "../helpers/cors";

/**
 * Story 25.2: Admin Manual Credits page E2E coverage.
 */

const mockLedger = [
	{
		transaction_id: 1,
		workspace_id: 42,
		actor_admin_id: "11111111-1111-4111-8111-111111111111",
		direction: "CREDIT",
		amount_credits: 500,
		amount_micros: 5_000_000,
		reason: "Manual top-up for partner",
		ticket_ref: "TICKET-1",
		created_at: new Date().toISOString(),
	},
	{
		transaction_id: 2,
		workspace_id: 42,
		actor_admin_id: "11111111-1111-4111-8111-111111111111",
		direction: "DEBIT",
		amount_credits: 100,
		amount_micros: 1_000_000,
		reason: "Clawback for duplicate charge",
		ticket_ref: "TICKET-2",
		created_at: new Date().toISOString(),
	},
];

async function setupAdminCreditsMocks(page: Page) {
	await mockAdminAuth(page);

	await page.route(/.*\/api\/v1\/admin\/credits\/ledger(\?.*)?$/, async (route: Route) => {
		await fulfillJson(route, 200, mockLedger);
	});

	await page.route(/.*\/api\/v1\/admin\/credits\/adjust$/, async (route: Route) => {
		await fulfillJson(route, 201, {
			transaction_id: 3,
			workspace_id: 42,
			actor_admin_id: "11111111-1111-4111-8111-111111111111",
			direction: "CREDIT",
			amount_credits: 100,
			amount_micros: 1_000_000,
			reason: "New adjustment",
			ticket_ref: "TICKET-3",
			idempotency_key: "new-idem",
			new_balance_credits: 500,
			created_at: new Date().toISOString(),
		});
	});
}

test.describe("Admin Credits page", () => {
	test.beforeEach(async ({ page }) => {
		await setupAdminCreditsMocks(page);
		await page.goto("/admin/credits");
	});

	test("renders four aggregate stat cards", async ({ page }) => {
		await expect(page.getByText("Total Credits Minted")).toBeVisible();
		await expect(page.getByText("Total Manual Debits")).toBeVisible();
		await expect(page.getByText("Today's Adjustments Count")).toBeVisible();
		await expect(page.getByText("High-Value Flags")).toBeVisible();
	});

	test("ledger rows are 36px tall", async ({ page }) => {
		await page.waitForSelector("table tbody tr");
		const firstRow = page.locator("table tbody tr").first();
		await expect(firstRow).toBeVisible();
		const box = await firstRow.boundingBox();
		expect(box).not.toBeNull();
		expect(box!.height).toBe(36);
	});

	test("export CSV downloads a file", async ({ page }) => {
		const [download] = await Promise.all([
			page.waitForEvent("download"),
			page.getByRole("button", { name: /Export CSV/i }).click(),
		]);

		expect(download.suggestedFilename()).toMatch(
			/^manual-credit-ledger-\d{4}-\d{2}-\d{2}\.csv$/,
		);
	});
});
