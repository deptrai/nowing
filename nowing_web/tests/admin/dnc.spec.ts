import type { Page, Route } from "@playwright/test";
import { expect, test } from "../fixtures";
import { fulfillJson } from "../helpers/cors";
import { mockAdminAuth } from "../helpers/admin-auth";

/**
 * Story 25.6: Global DNC (Do-Not-Call) & PII Blacklist Manager.
 *
 * Red-phase E2E scaffolds for `/admin/dnc`.
 */

const mockDncList = {
	items: [
		{
			id: "c3333333-3333-4333-8333-333333333333",
			record_type: "phone",
			value: "0908 *** 456",
			value_hmac: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
			reason: "Requested opt-out via Decree 13",
			source: "admin_manual",
			created_at: "2026-08-26T10:00:00Z",
		},
		{
			id: "d4444444-4444-4444-8444-444444444444",
			record_type: "domain",
			value: "spammer-network.vn",
			value_hmac: "7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
			reason: "Malicious crawler domain",
			source: "admin_manual",
			created_at: "2026-08-25T08:30:00Z",
		},
	],
	total: 2,
	limit: 50,
	offset: 0,
};


test.describe("Admin Global DNC Blacklist Manager (Story 25.6 ATDD)", () => {
	test.beforeEach(async ({ page }: { page: Page }) => {
		await mockAdminAuth(page);

		await page.route("**/api/v1/admin/dnc/**", async (route: Route) => {
			if (route.request().method() === "GET") {
				await fulfillJson(route, 200, mockDncList);
			} else if (route.request().method() === "POST") {
				await fulfillJson(route, 201, {
					id: "e5555555-5555-4555-8555-555555555555",
					record_type: "phone",
					value: "0912 *** 789",
					value_hmac: "abc1234567890",
					reason: "Opt-out",
					source: "admin_manual",
				});
			} else if (route.request().method() === "DELETE") {
				await fulfillJson(route, 204, {});
			}
		});
	});

	test("[P0] should render global DNC records list with masked values", async ({
		page,
	}: {
		page: Page;
	}) => {
		await page.goto("/admin/dnc");
		await expect(page.getByText("Global DNC Blacklist Registry")).toBeVisible();
		await expect(page.getByRole("cell", { name: "0908 *** 456" })).toBeVisible();
		await expect(page.getByRole("cell", { name: "spammer-network.vn" })).toBeVisible();
	});

	test("[P1] should add a new global phone DNC entry via modal", async ({
		page,
	}: {
		page: Page;
	}) => {
		await page.goto("/admin/dnc");
		await page.getByRole("button", { name: /add entry/i }).click();
		await page.locator("#new-dnc-type").selectOption("phone");
		await page.locator("#new-dnc-val").fill("0912345789");
		await page.locator("#new-dnc-reason").fill("Opt-out request");
		await page.getByRole("button", { name: /add to blacklist/i }).click();
	});

	test("[P1] should import CSV file in bulk modal", async ({ page }: { page: Page }) => {
		await page.goto("/admin/dnc");
		await page.getByRole("button", { name: /import csv/i }).click();
		await expect(page.getByText("Bulk CSV Blacklist Import")).toBeVisible();
	});

	test("[P2] should delete a DNC blacklist record", async ({ page }: { page: Page }) => {
		page.on("dialog", (dialog) => dialog.accept());
		await page.goto("/admin/dnc");
		const deleteBtn = page.getByTitle("Delete from global blacklist").first();
		await deleteBtn.click();
	});
});
