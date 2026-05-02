import { test, expect } from "../support/merged-fixtures";

/**
 * E2E tests — Authentication flows
 *
 * Covers P0-P1 authentication scenarios:
 *   P0: Dashboard loads for authenticated user
 *   P0: Unauthenticated access redirects to login
 *   P0: Login form submission navigates to dashboard
 *   P1: Logout clears session and redirects to login
 */

test.describe("Authentication", () => {
	// ---------------------------------------------------------------------------
	// P0 — Authenticated dashboard access
	// ---------------------------------------------------------------------------

	test("should display dashboard after login", async ({
		page,
		authToken,
		interceptNetworkCall,
		log,
	}) => {
		// Given — intercept API calls before navigation
		const meCall = interceptNetworkCall({ url: "**/api/users/me" });

		// When — navigate as authenticated user
		await log({ level: "step", message: "Navigate to dashboard" });
		await page.goto("/");

		// Then — verify API response and UI loaded
		const { responseJson, status } = await meCall;
		expect(status).toBe(200);
		expect(responseJson).toHaveProperty("id");

		// Dashboard container or heading is visible
		await expect(page.getByTestId("dashboard-heading").or(page.getByRole("main"))).toBeVisible();
	});

	// ---------------------------------------------------------------------------
	// P0 — Unauthenticated redirect
	// ---------------------------------------------------------------------------

	test("should redirect unauthenticated users to login", async ({ page }) => {
		// Given — no auth state (no storageState injection — bare page fixture)
		// When — navigate to protected route
		await page.goto("/");

		// Then — redirected to /login
		await expect(page).toHaveURL(/\/(login|auth)/);
		await expect(page.getByTestId("login-form").or(page.getByRole("form"))).toBeVisible({
			timeout: 10_000,
		});
	});

	// ---------------------------------------------------------------------------
	// P0 — Login form submit → dashboard
	// ---------------------------------------------------------------------------

	test("should navigate to dashboard after submitting login form", async ({ page, log }) => {
		const email = process.env.TEST_USER_EMAIL ?? "";
		const password = process.env.TEST_USER_PASSWORD ?? "";

		// Given — arrive at login page unauthenticated
		await page.goto("/login");
		await expect(page).toHaveURL(/\/(login|auth)/);

		// When — fill and submit the login form
		await log({ level: "step", message: "Fill credentials" });
		await page.getByTestId("login-email-input").or(page.getByLabel(/email/i)).fill(email);
		await page
			.getByTestId("login-password-input")
			.or(page.getByLabel(/password/i))
			.fill(password);

		await log({ level: "step", message: "Submit login" });
		await page
			.getByTestId("login-submit-button")
			.or(page.getByRole("button", { name: /sign in|log in|login/i }))
			.click();

		// Then — navigated away from login
		await expect(page).not.toHaveURL(/\/(login|auth)/, { timeout: 15_000 });
	});

	// ---------------------------------------------------------------------------
	// P1 — Logout
	// ---------------------------------------------------------------------------

	test("should clear session and redirect to login after logout", async ({
		page,
		authToken,
		interceptNetworkCall,
		log,
	}) => {
		// Given — authenticated user on dashboard
		await page.goto("/");
		await page.waitForURL(/^(?!.*\/(login|auth))/, { timeout: 15_000 });

		// When — trigger logout action
		await log({ level: "step", message: "Trigger logout" });

		// Try common logout patterns
		const logoutButton = page
			.getByTestId("logout-button")
			.or(page.getByRole("button", { name: /logout|sign out/i }));

		// Open user menu if logout is nested
		const userMenu = page
			.getByTestId("user-menu-button")
			.or(page.getByRole("button", { name: /profile|account|user/i }));

		if (await userMenu.isVisible()) {
			await userMenu.click();
		}

		await logoutButton.click({ timeout: 10_000 });

		// Then — redirected to login and token cleared
		await expect(page).toHaveURL(/\/(login|auth)/, { timeout: 15_000 });

		// Verify localStorage token is cleared
		const token = await page.evaluate(() => localStorage.getItem("nowing_access_token"));
		expect(token).toBeNull();
	});

	// ---------------------------------------------------------------------------
	// P1 — Invalid credentials
	// ---------------------------------------------------------------------------

	test("should show error message for invalid credentials", async ({ page, log }) => {
		// Given — login page
		await page.goto("/login");

		// When — submit wrong password
		await log({ level: "step", message: "Submit invalid credentials" });
		await page
			.getByTestId("login-email-input")
			.or(page.getByLabel(/email/i))
			.fill("invalid@example.com");
		await page
			.getByTestId("login-password-input")
			.or(page.getByLabel(/password/i))
			.fill("wrong-password-12345");

		await page
			.getByTestId("login-submit-button")
			.or(page.getByRole("button", { name: /sign in|log in|login/i }))
			.click();

		// Then — error feedback shown and still on login page
		await expect(page).toHaveURL(/\/(login|auth)/, { timeout: 10_000 });
		await expect(
			page
				.getByTestId("login-error")
				.or(page.getByRole("alert"))
				.or(page.getByText(/invalid|incorrect|wrong|error/i))
		).toBeVisible({ timeout: 10_000 });
	});
});
