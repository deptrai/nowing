import { expect, test } from "../fixtures";

/**
 * Story 22.3 (AC-5): Admin Scraper UI Telegram Tab & Live Cooldown Countdown.
 *
 * Validates:
 * - Telegram accounts list with Active, Rate-Limited, Cooldown badges
 * - Dynamic countdown timer for FloodWait cooling down accounts
 * - Multi-step OTP / 2FA onboarding modal
 * - Realtime channel stream toggle switch
 */

test.describe("Admin Scraper Accounts - Telegram Tab", () => {
	test("[P0] should render Telegram account tab with status pills and token quota", async ({
		page,
	}) => {
		await page.goto("/admin/scraper-accounts");

		// Click on Telegram tab
		const telegramTab = page.getByRole("tab", { name: /telegram/i });
		await expect(telegramTab).toBeVisible();
		await telegramTab.click();

		// Check table headers
		await expect(page.getByRole("columnheader", { name: /phone number/i })).toBeVisible();
		await expect(page.getByRole("columnheader", { name: /status/i })).toBeVisible();
		await expect(page.getByRole("columnheader", { name: /token quota/i })).toBeVisible();

		// Check status pill rendering
		await expect(page.getByTestId("account-status-badge").first()).toBeVisible();
	});

	test("[P0] should display live countdown timer for accounts in FloodWait cooldown", async ({
		page,
	}) => {
		await page.goto("/admin/scraper-accounts");

		const telegramTab = page.getByRole("tab", { name: /telegram/i });
		await telegramTab.click();

		// Check cooldown timer element for flood-waited accounts
		const cooldownBadge = page.getByTestId("cooldown-timer-badge");
		await expect(cooldownBadge).toBeVisible();
		await expect(cooldownBadge).toContainText(/Cooldown \(\d+s\)/i);
	});

	test("[P0] should open multi-step OTP / 2FA onboarding modal and advance steps", async ({
		page,
	}) => {
		await page.goto("/admin/scraper-accounts");

		const telegramTab = page.getByRole("tab", { name: /telegram/i });
		await telegramTab.click();

		// Click "Add Telegram Account" button
		const addAccountBtn = page.getByRole("button", {
			name: /add telegram account|connect telegram/i,
		});
		await addAccountBtn.click();

		// Step 1: Credentials
		const modal = page.getByRole("dialog");
		await expect(modal).toBeVisible();
		await expect(modal.getByLabel(/phone number/i)).toBeVisible();
		await expect(modal.getByLabel(/telegram api id/i)).toBeVisible();
		await expect(modal.getByLabel(/api hash/i)).toBeVisible();

		// Fill Step 1
		await modal.getByLabel(/phone number/i).fill("+84912345678");
		await modal.getByLabel(/telegram api id/i).fill("20401234");
		await modal.getByLabel(/api hash/i).fill("9ab8c7d6e5f4a3b2c1d0e9f8a7b6c5d4");

		// Click Send Auth Code
		const sendCodeBtn = modal.getByRole("button", { name: /send auth code|send code/i });
		await sendCodeBtn.click();

		// Step 2: Verification Code & 2FA
		await expect(modal.getByLabel(/verification code|code/i)).toBeVisible();
	});

	test("[P1] should toggle realtime stream for monitored channels", async ({ page }) => {
		await page.goto("/admin/scraper-accounts");

		const channelsTab = page.getByRole("tab", { name: /channels|monitored channels/i });
		await channelsTab.click();

		// Check stream toggle
		const streamToggle = page.getByTestId("channel-stream-toggle").first();
		await expect(streamToggle).toBeVisible();
	});
});
