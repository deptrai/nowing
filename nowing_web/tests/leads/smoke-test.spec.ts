import { expect, test } from "@playwright/test";

/**
 * E2E Playwright for Story 26.29 Smoke Test Feedback Loop.
 * Run: pnpm exec playwright test tests/leads/smoke-test.spec.ts
 */

test.describe("Smoke Test Feedback Loop (Story 26.29)", () => {
	test.use({ baseURL: process.env.BASE_URL || "http://localhost:3000" });

	test("PlanSummaryCard renders smoke test preview and feedback banner", async ({ page }) => {
		await page.goto("/dashboard/1/new-chat");

		// Open quickstart playbook builder (if available from chat)
		await page.getByRole("button", { name: /playbook/i }).first().click();

		// Select a preset
		await page.getByText(/Nhà phố Hà Nội/i).first().click();
		await page.getByRole("button", { name: /Tiếp theo|Next/i }).click();

		// Build a plan preview
		await page.getByTestId("btn-generate-plan").click();
		await expect(page.getByTestId("plan-summary-card")).toBeVisible();

		// Run smoke test
		await page.getByTestId("btn-smoke-test").click();
		await expect(page.getByTestId("location-feedback-banner")).toBeVisible({ timeout: 15000 });

		// Confirm 5 refinement options
		await expect(page.getByTestId("btn-confirm-full-run")).toBeVisible();
		await expect(page.getByTestId("btn-refine-narrow")).toBeVisible();
		await expect(page.getByTestId("btn-refine-expand")).toBeVisible();
		await expect(page.getByTestId("btn-refine-switch-source")).toBeVisible();
		await expect(page.getByTestId("btn-refine-custom-location")).toBeVisible();
	});
});
