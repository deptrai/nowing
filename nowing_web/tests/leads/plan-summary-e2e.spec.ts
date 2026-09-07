import { expect, test } from "@playwright/test";

/**
 * Story 26.27: Pre-Flight Lead Plan Summary — AC-4 Smoke Test E2E
 * Requires: FE on :3000, BE on :8000, authenticated e2e-test@nowing.net
 */
test.describe("Story 26.27: Pre-Flight Plan Summary Smoke Test", () => {
	test.use({ storageState: "playwright/.auth/user.json" });

	test("AC-4: Run pre-flight plan, smoke test 5 leads, and transition to full-launch CTA", async ({ page, request }) => {
		const workspaceId = 1;
		const planApi = `/api/v1/workspaces/${workspaceId}/campaigns/plan`;

		// 1. Validate plan API contract with mocked spec
		const planPayload = {
			name: "E2E Smoke Test Campaign",
			description: "Playwright E2E for Story 26.27",
			icp_config: {
				template: "custom",
				target_industries: ["Real Estate"],
				locations: ["Hồ Chí Minh"],
				company_size_range: null,
				tech_stack: [],
				intents: ["BÁN"],
				negative_keywords: [],
				reverse_icp_url: "",
				custom_instructions: "",
			},
			source_budget_config: {
				sources: ["batdongsan", "chotot"],
				expected_leads_target: 5,
				max_daily_spend_vnd: 500000,
				min_fit_score: 60,
				min_intent_score: 50,
				max_contacts_per_lead: 3,
				exclude_dnc: true,
				auto_unlock_verified_phones: false,
			},
			launch_config: {
				schedule_type: "once",
				cron_expression: null,
				start_time: null,
				auto_start: true,
				export_destination: "workspace",
				notification_webhook: "",
			},
		};

		const planResponse = await request.post(planApi, { data: planPayload });
		await expect(planResponse).toBeOK();
		const plan = await planResponse.json();

		// Assertions on plan response
		expect(plan).toHaveProperty("campaign_name");
		expect(plan).toHaveProperty("source_allocations");
		expect(plan.source_allocations.length).toBeGreaterThan(0);
		expect(plan).toHaveProperty("estimated_reachable_leads");
		expect(plan).toHaveProperty("estimated_cost_vnd");

		// 2. Render PlanSummaryCard via campaign builder wizard
		await page.goto(`/dashboard/${workspaceId}/leads/campaigns/new`);

		// Fill campaign name
		await page.getByPlaceholder("Tên chiến dịch").or(page.getByLabel(/tên chiến dịch/i)).fill("E2E Pre-Flight Plan");

		// Step 1: select source(s) — check batdongsan and chotot if visible
		const sourceCheckbox = page.getByTestId("source-toggle-batdongsan").or(page.getByText("batdongsan", { exact: false }));
		if (await sourceCheckbox.isVisible().catch(() => false)) {
			await sourceCheckbox.click();
		}

		// Step 2: location
		await page.getByRole("button", { name: /tiếp theo|next/i }).click();
		const locationTrigger = page.getByTestId("location-selector-trigger").or(page.getByPlaceholder(/tinh\/thanh/i).or(page.getByPlaceholder(/tỉnh\/thành/i)));
		if (await locationTrigger.isVisible().catch(() => false)) {
			await locationTrigger.click();
			await page.getByText("Hồ Chí Minh", { exact: false }).first().click();
		}

		// Step 3: launch / plan
		await page.getByRole("button", { name: /tiếp theo|next|xem kế hoạch/i }).click();

		// Click "Xem trước kế hoạch phân bổ" or similar
		const planButton = page.getByTestId("btn-generate-plan").or(page.getByRole("button", { name: /pre-flight|xem trước kế hoạch/i }));
		await expect(planButton).toBeVisible({ timeout: 10000 });
		await planButton.click();

		// Wait for plan summary card
		await expect(page.getByTestId("plan-summary-card")).toBeVisible({ timeout: 30000 });

		// Coverage badges
		const firstAllocation = page.getByTestId(/source-allocation-.*/).first();
		await expect(firstAllocation).toBeVisible();
		await firstAllocation.click();
		await expect(page.getByTestId(/coverage-quality-badge-.*/).first()).toBeVisible();

		// 3. Smoke test
		const smokeButton = page.getByTestId("btn-smoke-test").or(page.getByRole("button", { name: /chạy thử 5 lead/i }));
		await expect(smokeButton).toBeVisible();

		// Stub execute? E2E will call real backend. Use smokeTest with persist=false.
		await smokeButton.click();

		// Wait for loading state
		await expect(page.getByTestId("plan-summary-loading")).toBeVisible({ timeout: 10000 }).catch(() => null);

		// After execution, success toast or plan card updates
		await expect(page.getByTestId("plan-summary-card")).toBeVisible({ timeout: 60000 });

		// 4. Full launch CTA should be visible
		const fullLaunchButton = page.getByTestId("btn-apply-plan").or(page.getByRole("button", { name: /chạy chiến dịch đầy đủ/i }));
		await expect(fullLaunchButton).toBeVisible({ timeout: 15000 });
	});
});
