import { expect, test } from "../fixtures";

/**
 * Public login page smoke tests.
 *
 * Covers the unauthenticated surface that does not depend on the backend:
 * form rendering, password visibility toggle, and navigation to registration.
 * Authenticated journeys belong under tests/<feature>/.
 *
 * The app picks a locale from localStorage (`nowing-locale`), falling back to
 * timezone + navigator detection (Vietnam timezones force "vi"). Pin all three
 * to English so assertions stay semantic instead of per-locale.
 */
test.describe("Login page", () => {
	test.use({
		locale: "en-US",
		timezoneId: "America/New_York",
		storageState: {
			cookies: [],
			origins: [
				{
					origin: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
					localStorage: [{ name: "nowing-locale", value: "en" }],
				},
			],
		},
	});

	test("renders the sign-in form", async ({ page }) => {
		await page.goto("/login");

		await expect(page.getByRole("textbox", { name: "Email" })).toBeVisible();
		await expect(page.getByRole("textbox", { name: "Password" })).toBeVisible();
		await expect(
			page.getByRole("button", { name: /sign in/i }).first()
		).toBeVisible();
	});

	test("password visibility toggle reveals the password", async ({ page }) => {
		await page.goto("/login");

		const password = page.getByRole("textbox", { name: "Password" });
		await expect(password).toHaveAttribute("type", "password");

		await page.getByRole("button", { name: /show password/i }).click();
		await expect(password).toHaveAttribute("type", "text");

		await page.getByRole("button", { name: /hide password/i }).click();
		await expect(password).toHaveAttribute("type", "password");
	});

	test("links to registration stay on public routes", async ({ page }) => {
		await page.goto("/login");

		const registerLink = page.getByRole("link", { name: /sign up|register|create account/i });
		if (await registerLink.count()) {
			await registerLink.first().click();
			await expect(page).toHaveURL(/register|sign-up|signup/i);
		}
	});
});
