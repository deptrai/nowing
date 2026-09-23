import type { Page, Route } from "@playwright/test";
import { expect, test } from "../fixtures";
import { fulfillJson } from "../helpers/cors";
import { ADMIN_USER_ID, mockAdminAuth } from "../helpers/admin-auth";
import { mockWorkspaceReady } from "../helpers/workspace-mock";

/**
 * Story 25.6: In-App Broadcast Announcements Admin & Dashboard Banner.
 *
 * Red-phase E2E scaffolds for `/admin/broadcasts` and top `BroadcastBanner`.
 */

const mockBroadcastsList = {
	items: [
		{
			id: "f6666666-6666-4666-8666-666666666666",
			title: "Planned Maintenance Window",
			message: "We will perform scheduled updates on Sunday from 02:00 to 03:00 UTC.",
			banner_type: "maintenance",
			target_all: true,
			target_workspace_ids: [],
			starts_at: "2026-08-26T00:00:00Z",
			expires_at: "2026-08-28T00:00:00Z",
			dismissible: true,
			is_active: true,
			status: "active",
			created_at: "2026-08-26T00:00:00Z",
		},
		{
			id: "f7777777-7777-4777-8777-777777777777",
			title: "Special Summer Promotion",
			message: "Upgrade to Pro plan and get 20% extra AI credits!",
			banner_type: "promo",
			target_all: false,
			target_workspace_ids: [1],
			starts_at: "2026-08-20T00:00:00Z",
			expires_at: "2026-08-25T00:00:00Z",
			dismissible: true,
			is_active: true,
			status: "expired",
			created_at: "2026-08-20T00:00:00Z",
		},
	],
	total: 2,
};

const mockActiveBroadcasts = [
	{
		id: "f6666666-6666-4666-8666-666666666666",
		title: "Planned Maintenance Window",
		message: "We will perform scheduled updates on Sunday from 02:00 to 03:00 UTC.",
		banner_type: "maintenance",
		dismissible: true,
	},
];


test.describe("Broadcast Announcements Management & In-App Banner (Story 25.6 ATDD)", () => {
	test.beforeEach(async ({ page }: { page: Page }) => {
		await mockAdminAuth(page);
		await mockWorkspaceReady(page);

		await page.route("**/api/v1/admin/broadcasts*", async (route) => {
			if (route.request().method() === "GET") {
				await fulfillJson(route, 200, mockBroadcastsList);
			} else if (route.request().method() === "POST") {
				await fulfillJson(route, 201, {
					id: "f8888888-8888-4888-8888-888888888888",
					title: "New Announcement",
					message: "Important notice",
					banner_type: "info",
					target_all: true,
					target_workspace_ids: [],
					status: "active",
					is_active: true,
					dismissible: true,
				});
			} else if (route.request().method() === "DELETE") {
				await fulfillJson(route, 204, {});
			}
		});

		await page.route("**/api/v1/broadcasts/active*", async (route) => {
			await fulfillJson(route, 200, mockActiveBroadcasts);
		});
	});

	test("[P0] should render broadcast announcements admin list with status badges", async ({
		page,
	}: {
		page: Page;
	}) => {
		await page.goto("/admin/broadcasts");
		await expect(page.getByRole("heading", { name: /broadcasts|announcements/i })).toBeVisible();
		await expect(page.getByRole("cell", { name: "Planned Maintenance Window" })).toBeVisible();
		await expect(page.getByRole("cell", { name: "Special Summer Promotion" })).toBeVisible();
		await expect(page.getByText(/active/i).first()).toBeVisible();
		await expect(page.getByText(/expired/i)).toBeVisible();
	});

	test("[P1] should open create broadcast modal and submit new announcement", async ({
		page,
	}: {
		page: Page;
	}) => {
		await page.goto("/admin/broadcasts");
		await page.getByRole("button", { name: /new broadcast/i }).click();
		await page.locator("#broadcast-title").fill("Urgent Security Notice");
		await page.locator("#broadcast-message").fill("Please rotate your API keys.");
		await page.locator("#broadcast-banner-type").selectOption("warning");
		await page.getByRole("button", { name: /save announcement/i }).click();
	});

	test("[P0] should display in-app BroadcastBanner on dashboard and dismiss via close button", async ({
		page,
	}: {
		page: Page;
	}) => {
		await page.goto("/admin/broadcasts");
		const banner = page.getByText("Planned Maintenance Window").first();
		await expect(banner).toBeVisible();

		// Click dismiss button on the top BroadcastBanner
		const bannerContainer = page.locator("[data-testid^='broadcast-banner-']").first();
		await expect(bannerContainer).toBeVisible();
		const closeButton = bannerContainer.getByRole("button", { name: /dismiss/i });
		await expect(closeButton).toBeVisible();
		await closeButton.click();
		await expect(bannerContainer).not.toBeVisible();
	});
});
