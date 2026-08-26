import { expect, test } from "@playwright/test";

/**
 * Story 27.2b: Speaker Diarization Meeting Minutes from Chat
 * E2E Acceptance Tests.
 *
 * AC-1: Chat Session in Meeting Minutes Mode
 * AC-2: Transcription with Speaker Diarization
 * AC-3: Graceful Degradation
 * AC-5: Feature Gating
 */

test.describe("Story 27.2b — Meeting Minutes from Chat", () => {
	test.beforeEach(async ({ page }) => {
		await page.goto("/dashboard/1/new-chat");
	});

	test("AC-1: quick chip creates meeting-minutes mode thread", async ({ page }) => {
		await expect(page.getByText(/Welcome back/i)).toBeVisible({ timeout: 30_000 });
		const chip = page.getByRole("button", { name: /Summarize a meeting/i });
		await expect(chip).toBeVisible({ timeout: 30_000 });
		await chip.click();

		// URL should contain mode.
		await expect(page).toHaveURL(/[?&]mode=meeting_minutes/);

		// Composer should show the prompt placeholder text as input value.
		const composer = page.locator('[role="textbox"]').first();
		await expect(composer).toHaveText(/Paste the meeting recording URL here/i);
	});

	test("AC-1: slash prompt /meeting sets meeting-minutes mode", async ({ page }) => {
		const composer = page.locator('[role="textbox"]').first();
		await composer.fill("/meeting");

		// Pick the /meeting suggestion.
		const meetingItem = page.getByRole("button", { name: /\/meeting/i });
		await expect(meetingItem).toBeVisible();
		await meetingItem.click();

		await expect(page).toHaveURL(/[?&]mode=meeting_minutes/);
	});

	test.skip("AC-2: deliverable card shows processing then ready with speaker labels", async ({
		page,
	}) => {
		await page.goto("/dashboard/1/new-chat?mode=meeting_minutes");

		const composer = page.locator('[role="textbox"]').first();
		await composer.fill("https://example.com/sample-meeting.mp3");
		await page.keyboard.press("Enter");

		// Card starts in processing.
		await expect(page.getByText(/Processing/i)).toBeVisible();

		// Card eventually becomes ready and shows speakers.
		await expect(page.getByText(/Speaker 1/i)).toBeVisible({ timeout: 30_000 });
		await expect(page.getByText(/Action Items/i)).toBeVisible();
	});

	test.skip("AC-3: degraded card shows single-speaker transcript when diarization unavailable", async ({
		page,
	}) => {
		await page.goto("/dashboard/1/new-chat?mode=meeting_minutes");

		const composer = page.locator('[role="textbox"]').first();
		await composer.fill("https://example.com/no-diarization.mp3");
		await page.keyboard.press("Enter");

		await expect(
			page.getByText(/Transcript ready, but speaker labels are unavailable/i)
		).toBeVisible({ timeout: 30_000 });
		await expect(page.getByText(/Speaker 1/i)).toBeVisible();
	});

	test.skip("AC-5: 403 shown when Meeting Minutes feature is disabled", async ({ page }) => {
		// Feature off globally.
		await page.goto("/dashboard/1/new-chat?mode=meeting_minutes&meeting_minutes_enabled=false");

		await expect(
			page.getByText(/Meeting Minutes is not enabled on this workspace plan/i)
		).toBeVisible();
	});
});
