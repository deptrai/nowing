import { expect, test } from "@playwright/test";

test.describe("Story 23.2: Split-Pane ZNS Outreach Modal", () => {
	test.skip("opens split-pane modal and previews live ZNS message (Red Phase)", async ({
		page,
	}) => {
		// 1. Navigate to Leads table
		await page.goto("/dashboard/1/leads");

		// 2. Click ZNS Outreach button on a lead row
		const znsButton = page.locator('button:has-text("⚡ Gửi ZNS")').first();
		await expect(znsButton).toBeVisible();
		await znsButton.click();

		// 3. Verify Split-Pane Modal appears
		const modal = page.locator('[data-testid="zns-outreach-modal"]');
		await expect(modal).toBeVisible();

		// 4. Verify Left Pane: Template selector and dynamic variable inputs
		const templateSelect = page.locator('[data-testid="zns-template-select"]');
		await expect(templateSelect).toBeVisible();

		const customerNameInput = page.locator('input[name="customer_name"]');
		await expect(customerNameInput).toBeVisible();

		// 5. Verify Right Pane: Mobile mockup preview
		const mobileMockup = page.locator('[data-testid="zns-mobile-mockup"]');
		await expect(mobileMockup).toBeVisible();
		await expect(mobileMockup).toContainText("Zalo Notification Service");
	});
});
