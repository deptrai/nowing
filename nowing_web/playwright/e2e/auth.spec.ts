import { test, expect } from "../support/merged-fixtures";

/**
 * Example E2E test — Login flow
 *
 * Demonstrates:
 *   - Given/When/Then format
 *   - data-testid selector strategy
 *   - Network interception
 *   - Auth fixture usage
 */
test.describe("Authentication", () => {
	test("should display dashboard after login", async ({
		page,
		authToken,
		interceptNetworkCall,
		log,
	}) => {
		// Given — intercept API calls before navigation
		const meCall = interceptNetworkCall({ url: "**/api/me" });

		// When — navigate as authenticated user
		await log.step("Navigate to dashboard");
		await page.goto("/dashboard");

		// Then — verify API response and UI
		const { responseJson, status } = await meCall;
		expect(status).toBe(200);
		expect(responseJson).toHaveProperty("id");

		await expect(page.getByTestId("dashboard-heading")).toBeVisible();
	});

	test("should redirect unauthenticated users to login", async ({ page }) => {
		// Given — no auth state
		// When — navigate to protected route
		await page.goto("/dashboard");

		// Then — redirected to login
		await expect(page).toHaveURL(/\/login/);
		await expect(page.getByTestId("login-form")).toBeVisible();
	});
});
