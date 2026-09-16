import { expect, test } from "../fixtures";

async function mockWorkspaceSubscription(
	page: import("@playwright/test").Page,
	workspaceId: number,
	planTier: "free" | "team" | "growth" | "enterprise"
) {
	await page.route(`**/api/v1/workspaces/${workspaceId}/subscription`, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({
				workspace_id: workspaceId,
				plan_tier: planTier,
				current_plan: planTier,
				status: "active",
				effective_limits: {
					plan_tier: planTier,
				},
			}),
		});
	});
}

async function markWorkspaceSetupReady(page: import("@playwright/test").Page, workspaceId: number) {
	await page.route(`**/api/v1/workspaces/${workspaceId}/llm-setup-status`, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({
				status: "ready",
				source: "global_config",
				can_configure: true,
				stage: "ready",
			}),
		});
	});
}

/**
 * Story 27.2a: Presentation Studio from Chat (PPTX/Marp)
 * E2E Acceptance Tests.
 */

test.describe("Story 27.2a — Presentation Studio from Chat", () => {
	test("AC-1: quick chip creates presentation-studio mode thread", async ({ page, workspace }) => {
		await markWorkspaceSetupReady(page, workspace.id);
		await mockWorkspaceSubscription(page, workspace.id, "team");
		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		const chip = page.getByRole("button", { name: /pitch deck|pptx/i }).first();
		await expect(chip).toBeVisible({ timeout: 30_000 });
		await chip.click();

		await expect(page).toHaveURL(/[?&]mode=presentation_studio/);

		const composer = page.locator('[role="textbox"]').first();
		await expect(composer).toHaveText(/Create a 10-slide pitch deck|pitch deck/i);
	});

	test("AC-1: slash prompt /slides pptx sets presentation-studio mode", async ({
		page,
		workspace,
	}) => {
		await markWorkspaceSetupReady(page, workspace.id);
		await mockWorkspaceSubscription(page, workspace.id, "team");
		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		const composer = page.locator('[role="textbox"]').first();
		await composer.fill("/slides");

		const item = page.getByRole("button", { name: /\/slides pptx|pptx/i }).first();
		await expect(item).toBeVisible();
		await item.click();

		await expect(page).toHaveURL(/[?&]mode=presentation_studio/);
	});

	test("AC-2: deliverable card shows PPTX pitch deck ready", async ({ page, workspace }) => {
		test.setTimeout(300_000);
		await markWorkspaceSetupReady(page, workspace.id);
		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=presentation_studio`);

		const composer = page.locator('[role="textbox"]').first();
		await composer.click();
		await composer.type("Create a 5-slide pitch deck for Nowing", { delay: 10 });
		await composer.press("Enter");

		await expect(page.getByText(/Designing your slides|generating|creating/i).first()).toBeVisible({
			timeout: 60_000,
		});
		await expect(page.getByText(/Ready|ready/i).first()).toBeVisible({ timeout: 240_000 });
		await expect(page.getByText(/slides.*PPTX|PPTX|\.pptx/i).first()).toBeVisible({
			timeout: 240_000,
		});
		await expect(page.getByText(/Download.*pptx|\.pptx/i).first()).toBeVisible({ timeout: 30_000 });
	});

	test("AC-3: deliverable card shows Marp slides ready", async ({ page, workspace }) => {
		test.slow();
		await markWorkspaceSetupReady(page, workspace.id);
		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=presentation_studio`);

		const composer = page.locator('[role="textbox"]').first();
		await composer.click();
		await composer.type("Create a 5-slide Marp deck about AI productivity, output as marp", {
			delay: 10,
		});
		await composer.press("Enter");

		await expect(page.getByText(/Designing your slides|generating|creating/i).first()).toBeVisible({
			timeout: 60_000,
		});
		await expect(page.getByText(/slides.*MARP|Marp|marp/i).first()).toBeVisible({
			timeout: 180_000,
		});
	});

	test("AC-4: 403 shown when Presentation Studio feature is disabled", async ({
		page,
		workspace,
	}) => {
		await markWorkspaceSetupReady(page, workspace.id);
		await page.goto(
			`/dashboard/${workspace.id}/new-chat?mode=presentation_studio&presentation_studio_enabled=false`
		);

		await expect(
			page.getByText(/Presentation Studio is not enabled|not enabled|upgrade/i).first()
		).toBeVisible();
	});

	test.describe("Story 31.4 — Format Entitlement (PPTX vs Marp)", () => {
		test("AC-5: free tier hides PPTX slash command and keeps Marp", async ({ page, workspace }) => {
			await markWorkspaceSetupReady(page, workspace.id);
			await mockWorkspaceSubscription(page, workspace.id, "free");
			await page.goto(`/dashboard/${workspace.id}/new-chat`);

			const composer = page.locator('[role="textbox"]').first();
			await composer.fill("/slides");

			// /slides marp is offered
			await expect(page.getByRole("button", { name: /\/slides marp|marp/i }).first()).toBeVisible();
			// /slides pptx is NOT offered on free tier
			await expect(page.getByRole("button", { name: /\/slides pptx/i })).toHaveCount(0);
		});

		test("AC-6: free tier hides pitch deck quick chip in thread welcome", async ({
			page,
			workspace,
		}) => {
			await markWorkspaceSetupReady(page, workspace.id);
			await mockWorkspaceSubscription(page, workspace.id, "free");
			await page.goto(`/dashboard/${workspace.id}/new-chat`);

			// Pitch deck (PPTX) chip is hidden on free tier
			await expect(page.getByRole("button", { name: /pitch deck|pptx/i })).toHaveCount(0);
			// Marp slides chip remains visible
			await expect(page.getByRole("button", { name: /marp/i }).first()).toBeVisible();
		});

		test("AC-7: paid tier shows both PPTX and Marp in prompt picker and thread welcome", async ({
			page,
			workspace,
		}) => {
			await markWorkspaceSetupReady(page, workspace.id);
			await mockWorkspaceSubscription(page, workspace.id, "growth");
			await page.goto(`/dashboard/${workspace.id}/new-chat`);

			// Pitch deck chip is visible on paid tier
			await expect(page.getByRole("button", { name: /pitch deck/i }).first()).toBeVisible({
				timeout: 15_000,
			});

			const composer = page.locator('[role="textbox"]').first();
			await composer.fill("/slides");

			// Both /slides pptx and /slides marp are offered
			await expect(page.getByRole("button", { name: /\/slides pptx/i }).first()).toBeVisible();
			await expect(page.getByRole("button", { name: /\/slides marp/i }).first()).toBeVisible();
		});

		test("AC-8: free tier rewrites ?format=pptx and PPTX prompt to Marp once subscription resolves", async ({
			page,
			workspace,
		}) => {
			await markWorkspaceSetupReady(page, workspace.id);
			await mockWorkspaceSubscription(page, workspace.id, "free");

			const prompt = encodeURIComponent(
				"Create a 10-slide pitch deck as a PowerPoint PPTX file. Call generate_presentation with output_format=pptx."
			);
			await page.goto(
				`/dashboard/${workspace.id}/new-chat?mode=presentation_studio&format=pptx&q=${prompt}`
			);

			// URL rewritten to format=marp
			await expect(page).toHaveURL(/[?&]format=marp/);

			// Composer text rewritten from PPTX to Marp
			const composer = page.locator('[role="textbox"]').first();
			await expect(composer).not.toHaveText(/output_format=pptx/i);
			await expect(composer).toHaveText(/output_format=marp/i);
		});
	});
});
