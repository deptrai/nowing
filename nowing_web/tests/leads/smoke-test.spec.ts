import { expect, test } from "@playwright/test";
import { safeClick } from "../helpers/safe-click";

/**
 * E2E Playwright for Story 26.29 Smoke Test Feedback Loop.
 * Run: pnpm exec playwright test tests/leads/smoke-test.spec.ts
 */

test.describe("Smoke Test Feedback Loop (Story 26.29)", () => {
	test.use({
		baseURL: process.env.PLAYWRIGHT_BASE_URL || process.env.BASE_URL || "http://localhost:3000",
	});

	test("PlanSummaryCard renders smoke test preview and feedback banner", async ({ page }) => {
		// Mock campaign execution response so smoke test has leads in local test env
		await page.route("**/api/v1/workspaces/*/campaigns/execute*", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					status: "completed",
					total_discovered: 5,
					total_deduplicated: 5,
					leads: [
						{
							id: "lead-smoke-1",
							company_name: "Công ty BĐS Thăng Long E2E",
							title: "Bán nhà mặt phố Cầu Giấy",
							phone: "0908123456",
							location: "Hà Nội",
							fit_score: 95,
							source: "batdongsan",
						},
					],
					degraded_sources: [],
					subtask_plans: [],
					deduplication_summary: { raw_count: 5, deduplicated_count: 5, dnc_suppressed_count: 0 },
					execution_time_ms: 150,
					source_latency_ms: { batdongsan: 150 },
					deduplication_rate: 0,
					location_match_metadata: {
						matched_count: 1,
						outside_count: 0,
						fallback_province: false,
						unresolved_locations: [],
						feedback_state: "exact_match",
						suggested_actions: [],
					},
				}),
			});
		});

		await page.goto("/dashboard/1/new-chat");

		// Select the real-estate playbook preset from the new-chat page
		await page
			.getByRole("heading", { name: /Bất động sản|Real Estate/i })
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

		// Step 3: product / example (bilingual: VD / e.g.)
		const productInput = page.getByPlaceholder(/SaaS HR, Nhà phố, Senior Python/i);
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
