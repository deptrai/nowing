import { expect, test } from "@playwright/test";

/**
 * Story 27.2a: Presentation Studio from Chat (PPTX/Marp)
 * E2E Acceptance Tests.
 *
 * AC-1: Chat Session in Presentation Studio Mode
 * AC-2: PPTX pitch deck generation and download
 * AC-3: Marp Markdown generation and graceful degradation
 * AC-4: Feature gating
 */

test.describe("Story 27.2a — Presentation Studio from Chat", () => {
	test.beforeEach(async ({ page }) => {
		await page.goto("/dashboard/1/new-chat");
	});

	test("AC-1: quick chip creates presentation-studio mode thread", async ({ page }) => {
		await expect(page.getByText(/Welcome back/i)).toBeVisible({ timeout: 30_000 });

		const chip = page.getByRole("button", { name: /Create a pitch deck/i });
		await expect(chip).toBeVisible({ timeout: 30_000 });
		await chip.click();

		await expect(page).toHaveURL(/[?&]mode=presentation_studio/);

		const composer = page.locator('[role="textbox"]').first();
		await expect(composer).toHaveText(/Create a 10-slide pitch deck/i);
	});

	test("AC-1: slash prompt /slides pptx sets presentation-studio mode", async ({ page }) => {
		const composer = page.locator('[role="textbox"]').first();
		await composer.fill("/slides");

		const item = page.getByRole("button", { name: /\/slides pptx/i });
		await expect(item).toBeVisible();
		await item.click();

		await expect(page).toHaveURL(/[?&]mode=presentation_studio/);
	});

	test("AC-2: deliverable card shows PPTX pitch deck ready", async ({ page }) => {
		// Real LLM call may take > 2 min and the agent can retry once on
		// "Prompt exceeds maximum allowed length", so give the turn 5 min.
		test.setTimeout(300_000);
		await page.goto("/dashboard/1/new-chat?mode=presentation_studio");

		const composer = page.locator('[role="textbox"]').first();
		await composer.click();
		await composer.type("Create a 5-slide pitch deck for Nowing", { delay: 10 });
		await composer.press("Enter");

		await expect(page.getByText(/Designing your slides/i)).toBeVisible({ timeout: 60_000 });
		await expect(page.getByText(/Ready/i).first()).toBeVisible({ timeout: 240_000 });
		await expect(page.getByText(/slides · PPTX/i).first()).toBeVisible({ timeout: 240_000 });
		// The card renders the download as an <a> (link) in the chat stream.
		await expect(page.getByText(/Download \.pptx/i).first()).toBeVisible({ timeout: 30_000 });
	});

	test("AC-3: deliverable card shows Marp slides ready", async ({ page }) => {
		test.slow();
		await page.goto("/dashboard/1/new-chat?mode=presentation_studio");

		const composer = page.locator('[role="textbox"]').first();
		await composer.click();
		await composer.type("Create a 5-slide Marp deck about AI productivity, output as marp", {
			delay: 10,
		});
		await composer.press("Enter");

		await expect(page.getByText(/Designing your slides/i)).toBeVisible({ timeout: 60_000 });
		await expect(page.getByText(/slides · MARP/i)).toBeVisible({ timeout: 180_000 });
	});

	test("AC-4: 403 shown when Presentation Studio feature is disabled", async ({ page }) => {
		await page.goto(
			"/dashboard/1/new-chat?mode=presentation_studio&presentation_studio_enabled=false"
		);

		await expect(
			page.getByText(/Presentation Studio is not enabled on this workspace plan/i)
		).toBeVisible();
	});
});
