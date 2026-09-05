import { expect, test } from "../fixtures";

async function markWorkspaceSetupReady(
	page: import("@playwright/test").Page,
	workspaceId: number
) {
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
		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		const chip = page.getByRole("button", { name: /pitch deck|pptx/i }).first();
		await expect(chip).toBeVisible({ timeout: 30_000 });
		await chip.click();

		await expect(page).toHaveURL(/[?&]mode=presentation_studio/);

		const composer = page.locator('[role="textbox"]').first();
		await expect(composer).toHaveText(/Create a 10-slide pitch deck|pitch deck/i);
	});

	test("AC-1: slash prompt /slides pptx sets presentation-studio mode", async ({ page, workspace }) => {
		await markWorkspaceSetupReady(page, workspace.id);
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
		await expect(page.getByText(/slides.*PPTX|PPTX|\.pptx/i).first()).toBeVisible({ timeout: 240_000 });
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
		await expect(page.getByText(/slides.*MARP|Marp|marp/i).first()).toBeVisible({ timeout: 180_000 });
	});

	test("AC-4: 403 shown when Presentation Studio feature is disabled", async ({ page, workspace }) => {
		await markWorkspaceSetupReady(page, workspace.id);
		await page.goto(
			`/dashboard/${workspace.id}/new-chat?mode=presentation_studio&presentation_studio_enabled=false`
		);

		await expect(
			page.getByText(/Presentation Studio is not enabled|not enabled|upgrade/i).first()
		).toBeVisible();
	});
});
