import { expect, type Response, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * E2E acceptance tests for Story 24.6: Two-Way AI Outreach Auto-Reply Agent settings.
 */

test.describe("Auto-Reply messaging settings", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `ATDD Auto-Reply ${Date.now()}`);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	function waitForWorkspaceUpdate(page: (typeof test.arguments)[0]) {
		return page.waitForResponse(
			(response: Response) =>
				response.url().includes(`/api/v1/workspaces/${workspaceId}`) &&
				response.request().method() === "PUT" &&
				response.ok()
		);
	}

	test("owner can enable auto-reply and persist fallback + recipient", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/user-settings/messaging-channels`);

		const card = page.getByText("AI Tự Động Trả Lời Tin Nhắn 24/7").locator("xpath=../../..");
		await expect(card).toBeVisible();

		const toggle = card.getByTestId("auto-reply-toggle");
		await expect(toggle).toBeVisible();
		await expect(toggle).not.toBeChecked();

		const toggleResponse = await Promise.all([waitForWorkspaceUpdate(page), toggle.click()]);
		const toggleBody = (await toggleResponse[0].json()) as { auto_reply_enabled: boolean };
		expect(toggleBody.auto_reply_enabled).toBe(true);
		await expect(toggle).toBeChecked();

		const fallback = card.getByTestId("auto-reply-fallback");
		await expect(fallback).toBeVisible();
		await fallback.fill("Dạ em xin phép ghi nhận và chuyển chuyên viên tư vấn.");
		await fallback.blur();
		await waitForWorkspaceUpdate(page);

		const recipient = card.getByTestId("auto-reply-recipient");
		await expect(recipient).toBeVisible();
		await recipient.fill("@sales_alert_channel");
		await recipient.blur();
		await waitForWorkspaceUpdate(page);

		// State should survive a navigation away and back (avoids full reload race with zero-cache).
		await page.goto(`/dashboard/${workspaceId}/user-settings/profile`);
		await page.goto(`/dashboard/${workspaceId}/user-settings/messaging-channels`);

		const reloadedCard = page
			.getByText("AI Tự Động Trả Lời Tin Nhắn 24/7")
			.locator("xpath=../../..");
		await expect(reloadedCard).toBeVisible();
		const reloadedToggle = reloadedCard.getByTestId("auto-reply-toggle");
		const reloadedFallback = reloadedCard.getByTestId("auto-reply-fallback");
		const reloadedRecipient = reloadedCard.getByTestId("auto-reply-recipient");
		await expect(reloadedToggle).toBeChecked();
		await expect(reloadedFallback).toHaveValue(
			"Dạ em xin phép ghi nhận và chuyển chuyên viên tư vấn."
		);
		await expect(reloadedRecipient).toHaveValue("@sales_alert_channel");
	});
});
