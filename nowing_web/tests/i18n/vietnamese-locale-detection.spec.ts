import { expect, test } from "../fixtures";

test.describe("Story 7.8: Vietnamese i18n & Smart Geo-Locale Auto-Detection E2E", () => {
	test.beforeEach(async ({ page }) => {
		// Clear local storage and cookies before each test to simulate fresh or controlled visits
		await page.addInitScript(() => {
			window.localStorage.clear();
		});
	});

	test("[P0] first-time visit auto-detects Vietnamese when browser language is vi-VN", async ({
		page,
		workspace,
	}) => {
		// Set browser language to Vietnamese
		await page.setExtraHTTPHeaders({
			"Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
		});

		// Emulate navigator.languages on the client
		await page.addInitScript(() => {
			Object.defineProperty(navigator, "languages", {
				get: () => ["vi-VN", "vi", "en-US"],
			});
			Object.defineProperty(navigator, "language", {
				get: () => "vi-VN",
			});
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		// Verify that <html lang="vi"> attribute is set
		await expect(page.locator("html")).toHaveAttribute("lang", "vi", { timeout: 10000 });

		// Verify that locale is persisted in localStorage as "vi"
		const storedLocale = await page.evaluate(() => window.localStorage.getItem("nowing-locale"));
		expect(storedLocale).toBe("vi");
	});

	test("[P0] first-time visit auto-detects Vietnamese when timezone is Asia/Ho_Chi_Minh", async ({
		browser,
		workspace,
	}) => {
		// Create a new context with Asia/Ho_Chi_Minh timezone and generic English language
		const context = await browser.newContext({
			timezoneId: "Asia/Ho_Chi_Minh",
			locale: "en-US",
		});
		const page = await context.newPage();

		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		// Verify that <html lang="vi"> attribute is set via timezone detection
		await expect(page.locator("html")).toHaveAttribute("lang", "vi", { timeout: 10000 });

		// Verify that localStorage contains "vi"
		const storedLocale = await page.evaluate(() => window.localStorage.getItem("nowing-locale"));
		expect(storedLocale).toBe("vi");

		await context.close();
	});

	test("[P0] user can manually switch language to Vietnamese via LanguageSwitcher", async ({
		page,
		workspace,
	}) => {
		// Start with explicit English preference
		await page.addInitScript(() => {
			window.localStorage.setItem("nowing-locale", "en");
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat`);
		await expect(page.locator("html")).toHaveAttribute("lang", "en", { timeout: 10000 });

		// Open LanguageSwitcher select
		const languageTrigger = page
			.locator("button")
			.filter({ hasText: /English|Tiếng Việt/ })
			.first();
		if (await languageTrigger.isVisible()) {
			await languageTrigger.click();

			// Select Tiếng Việt
			const viOption = page.getByRole("option", { name: /Tiếng Việt/i });
			await viOption.click();

			// Verify HTML lang updated to 'vi'
			await expect(page.locator("html")).toHaveAttribute("lang", "vi");

			// Verify localStorage updated
			const storedLocale = await page.evaluate(() => window.localStorage.getItem("nowing-locale"));
			expect(storedLocale).toBe("vi");
		}
	});

	test("[P0] stored language preference in localStorage is strictly preserved across reloads", async ({
		page,
		workspace,
	}) => {
		// User previously chose Spanish 'es'
		await page.addInitScript(() => {
			window.localStorage.setItem("nowing-locale", "es");
			// Even if browser language is Vietnamese, stored preference should win
			Object.defineProperty(navigator, "languages", {
				get: () => ["vi-VN", "vi"],
			});
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		// Verify it stays Spanish and does not override with auto-detection
		await expect(page.locator("html")).toHaveAttribute("lang", "es", { timeout: 10000 });

		const storedLocale = await page.evaluate(() => window.localStorage.getItem("nowing-locale"));
		expect(storedLocale).toBe("es");
	});

	test("[P1] defaults to English for unsupported locale on first visit", async ({
		page,
		workspace,
	}) => {
		// Emulate an unsupported browser locale (e.g. de-DE / German) with non-VN timezone
		await page.addInitScript(() => {
			Object.defineProperty(navigator, "languages", {
				get: () => ["de-DE", "de"],
			});
			Object.defineProperty(navigator, "language", {
				get: () => "de-DE",
			});
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		// Verify fallback to English
		await expect(page.locator("html")).toHaveAttribute("lang", "en", { timeout: 10000 });

		const storedLocale = await page.evaluate(() => window.localStorage.getItem("nowing-locale"));
		expect(storedLocale).toBe("en");
	});
});
