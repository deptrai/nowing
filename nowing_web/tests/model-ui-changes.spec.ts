import { test, expect } from "@playwright/test";
import { mockAdminAuth } from "./helpers/admin-auth";
import { mockWorkspaceReady } from "./helpers/workspace-mock";

test.describe("Model UI simplification (Sprint Change Proposal 2026-09-01)", () => {
	test.beforeEach(async ({ page }) => {
		await mockAdminAuth(page);
		await mockWorkspaceReady(page);
	});

	test("chat header does not show image model selector", async ({ page }) => {
		await page.goto("/dashboard/1/new-chat");
		// The composer should render; there should be only one model selector trigger
		const modelSelectors = page.locator('button[aria-label="Select chat model"]').first();
		await expect(modelSelectors).toBeVisible();
		// Image model selector button should not exist
		await expect(page.locator('button[aria-label="Select image model"]').first()).not.toBeVisible();
	});

	test("model selector does not show Manage models button", async ({ page }) => {
		await page.goto("/dashboard/1/new-chat");
		await page.click('button[aria-label="Select chat model"]', { timeout: 15000 });
		await expect(page.getByRole("button", { name: /Manage models/i })).not.toBeVisible();
	});

	test("workspace settings does not show Models tab", async ({ page }) => {
		await page.goto("/dashboard/1/workspace-settings/general");
		await expect(page.getByRole("tab", { name: /Models/i })).not.toBeVisible();
	});
});
