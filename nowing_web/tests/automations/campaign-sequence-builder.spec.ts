import { expect, test } from "@playwright/test";

test.describe("Story 24.1: Multi-Channel Drip Outreach Campaign Engine (VisualCadenceBuilder & Analytics)", () => {
	test("AC-1: creates a multi-step sequence with send_email, wait, condition and email-only channel", async ({
		page,
	}) => {
		// 1. Navigate to New Campaign Builder
		await page.goto("/dashboard/1/automations/campaigns/new");

		// 2. Verify Cadence Builder Canvas is rendered
		const canvas = page.locator('[data-testid="sequence-cadence-builder"]');
		await expect(canvas).toBeVisible();

		// 3. Verify Channel Selector: Email is selectable, other channels are disabled with "deferred" tooltip
		const emailChannel = page.locator('[data-testid="channel-option-email"]');
		await expect(emailChannel).toBeEnabled();

		const zaloChannel = page.locator('[data-testid="channel-option-zalo"]');
		await expect(zaloChannel).toBeDisabled();
		await expect(zaloChannel).toHaveAttribute("data-deferred", "true");

		const telegramChannel = page.locator('[data-testid="channel-option-telegram"]');
		await expect(telegramChannel).toBeDisabled();

		// 4. Add Step 2: Send Email (step 1 is the initial default email node)
		const addEmailStepBtn = page.locator('[data-testid="add-step-send_email"]');
		await addEmailStepBtn.click();

		const emailStepNode = page.locator('[data-testid="step-node-2"]');
		await expect(emailStepNode).toBeVisible();

		// Check template variable pills inside the newly added email step
		const variablePills = emailStepNode.locator('[data-testid="template-variable-pills"]');
		await expect(variablePills).toContainText("{customer_name}");
		await expect(variablePills).toContainText("{company}");
		await expect(variablePills).toContainText("{property_title}");

		// 5. Add Step 3: Wait (Delay)
		const addWaitStepBtn = page.locator('[data-testid="add-step-wait"]');
		await addWaitStepBtn.click();

		const waitStepNode = page.locator('[data-testid="step-node-3"]');
		await expect(waitStepNode).toBeVisible();
		const waitDurationInput = waitStepNode.locator('[data-testid="wait-duration-input"]');
		await expect(waitDurationInput).toBeVisible();

		// 6. Add Step 4: Condition (Branch)
		const addConditionBtn = page.locator('[data-testid="add-step-condition"]');
		await addConditionBtn.click();

		const conditionNode = page.locator('[data-testid="step-node-4"]');
		await expect(conditionNode).toBeVisible();
		await expect(conditionNode).toContainText("if replied");

		// 7. Save Sequence
		const saveButton = page.locator('[data-testid="save-sequence-btn"]');
		await expect(saveButton).toBeEnabled();
		await saveButton.click();

		// Verify redirect to campaign list or details
		await expect(page).toHaveURL(/\/dashboard\/1\/automations\/campaigns/);
	});

	test("AC-8: displays sequence analytics with delivered, responded, unsubscribed and cost metrics", async ({
		page,
	}) => {
		// 1. Navigate to existing Campaign Analytics view
		await page.goto("/dashboard/1/automations/campaigns/test-seq-123");

		// 2. Verify Analytics Dashboard Header
		const analyticsHeader = page.locator('[data-testid="sequence-analytics-header"]');
		await expect(analyticsHeader).toBeVisible();

		// 3. Verify Metric Cards
		const totalEnrolled = page.locator('[data-testid="metric-total-enrolled"]');
		await expect(totalEnrolled).toBeVisible();

		const activeScheduled = page.locator('[data-testid="metric-active-scheduled"]');
		await expect(activeScheduled).toBeVisible();

		const deliveredCount = page.locator('[data-testid="metric-delivered-count"]');
		await expect(deliveredCount).toBeVisible();

		const respondedCount = page.locator('[data-testid="metric-responded-count"]');
		await expect(respondedCount).toBeVisible();

		const unsubscribedCount = page.locator('[data-testid="metric-unsubscribed-count"]');
		await expect(unsubscribedCount).toBeVisible();

		const totalCost = page.locator('[data-testid="metric-total-cost"]');
		await expect(totalCost).toBeVisible();
	});
});
