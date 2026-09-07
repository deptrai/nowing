import { expect, test } from "@playwright/test";
import { safeClick } from "../helpers/safe-click";

/**
 * E2E Playwright for Story 26.29 Smoke Test Feedback Loop.
 * Run: pnpm exec playwright test tests/leads/smoke-test.spec.ts
 */

test.describe("Smoke Test Feedback Loop (Story 26.29)", () => {
	test.use({ baseURL: process.env.BASE_URL || "http://localhost:3000" });

	test("PlanSummaryCard renders smoke test preview and feedback banner", async ({ page }) => {
		await page.goto("/dashboard/1/new-chat");

		// Select the real-estate playbook preset from the new-chat page
		await page
			.getByRole("heading", { name: /Bất động sản/i })
			.first()
			.click();

		// Step 1: confirm default intent (Buy / Mua)
		await expect(page.getByText(/Buy \/ Mua/i).first()).toBeVisible();
		await page
			.getByRole("button", { name: /Tiếp theo|Next/i })
			.first()
			.click();

		// Step 2: location — use the quick Hà Nội 1-click pill
		await page.getByRole("button", { name: "Hà Nội" }).first().click();
		await safeClick(page.getByRole("button", { name: /Tiếp theo|Next/i }).first());

		// Step 3: product / example
		const productInput = page.getByPlaceholder(/VD: SaaS HR, Nhà phố, Senior Python/i);
		await productInput.fill("Nhà phố Hà Nội");
		await safeClick(page.getByRole("button", { name: /Tiếp theo|Next/i }).first());

		// Step 4: channels (defaults are pre-selected)
		await safeClick(page.getByRole("button", { name: /Tiếp theo|Next/i }).first());

		// Step 5: preview & plan
		await expect(page.getByTestId("btn-generate-plan")).toBeVisible({ timeout: 30000 });
		await safeClick(page.getByTestId("btn-generate-plan"));
		await expect(page.getByTestId("plan-summary-card")).toBeVisible({ timeout: 30000 });

		// Run smoke test
		await safeClick(page.getByTestId("btn-smoke-test"));
		await expect(page.getByTestId("location-feedback-banner")).toBeVisible({ timeout: 60000 });

		// Confirm 5 refinement options
		await expect(page.getByTestId("btn-confirm-full-run")).toBeVisible();
		await expect(page.getByTestId("btn-refine-narrow")).toBeVisible();
		await expect(page.getByTestId("btn-refine-expand")).toBeVisible();
		await expect(page.getByTestId("btn-refine-switch-source")).toBeVisible();
		await expect(page.getByTestId("btn-refine-custom-location")).toBeVisible();
	});
});
