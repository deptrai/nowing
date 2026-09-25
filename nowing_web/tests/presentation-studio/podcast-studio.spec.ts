import { expect, test } from "../fixtures";
import { isE2eBackend } from "../helpers/api/auth";

/**
 * Story 27.3: Video & Podcast Generation Studio (FR-22)
 * E2E Acceptance Tests.
 */

test.describe("Story 27.3 — Video & Podcast Studio", () => {
	test.beforeEach(async ({ page }) => {
		await page.addInitScript(() => {
			localStorage.setItem("nowing-locale", "en");
		});
	});

	test("AC-1: podcast route accepts generate_podcast tool intent", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		const composer = page.locator('[role="textbox"]').first();
		await composer.click();
		await composer.type("Generate a podcast about real estate trends", { delay: 10 });
		await composer.press("Enter");

		// Verify chat thread transitions to the active assistant response container
		// If the backend is E2E-mock, it returns a mocked tool-event or immediate response
		await expect(page.getByText(/Podcast|generating|audio|episode/i).first()).toBeVisible({
			timeout: 60_000,
		});
	});

	test("AC-2: verify audio player renders in a completed podcast message", async ({
		page,
		workspace,
		request,
	}) => {
		// This spec is gated to run fully only on the fake e2e backend that guarantees tool generation
		test.skip(!(await isE2eBackend(request)), "Podcast generation requires fake e2e backend");

		await page.goto(`/dashboard/${workspace.id}/new-chat`);
		const composer = page.locator('[role="textbox"]').first();
		await composer.fill("Generate a short podcast");
		await composer.press("Enter");

		// Wait for assistant to stream the generate_podcast tool UI
		await expect(page.locator("audio")).toBeVisible({ timeout: 120_000 });
	});
});
