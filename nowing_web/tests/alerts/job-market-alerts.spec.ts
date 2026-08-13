import { expect, test } from "@playwright/test";

/**
 * E2E for Story 12.9 — Job Market Alerts.
 *
 * Verifies the grouped alert notification flow end-to-end against the real
 * backend/frontend stack:
 *   - Authenticate with a seeded user that has an alert_run_complete notification.
 *   - Open the notifications popover.
 *   - See the grouped alert entry (rule name + match count).
 *   - Click it and navigate to the saved search detail with the snapshot query.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
const FRONTEND_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const SESSION_COOKIE_NAME = process.env.SESSION_COOKIE_NAME || "nowing_session";

test.describe("Job Market Alerts", () => {
	test("grouped alert notification navigates to saved search snapshot", async ({
		page,
		request,
	}) => {
		// 1. Acquire an access token for the seeded e2e alert user.
		const login = await request.post(`${BACKEND_URL}/auth/desktop/login`, {
			data: {
				email: "e2e-test@nowing.net",
				password: "E2eTestPassword123!",
			},
			headers: { "Content-Type": "application/json", Origin: FRONTEND_URL },
		});
		expect(login.ok()).toBeTruthy();
		const { access_token } = (await login.json()) as { access_token: string };
		expect(access_token).toBeTruthy();

		await page.context().addCookies([
			{
				name: SESSION_COOKIE_NAME,
				value: access_token,
				url: FRONTEND_URL,
				httpOnly: true,
				sameSite: "Lax",
			},
		]);

		// 2. Load the dashboard and open the notifications popover.
		await page.goto(`${FRONTEND_URL}/dashboard`);
		const bell = page.locator('button[aria-label="Notifications"]').first();
		await expect(bell).toBeVisible({ timeout: 30_000 });
		await bell.click();

		// Wait for the popover panel to render.
		await expect(page.locator("text=Notifications").first()).toBeVisible({ timeout: 15_000 });

		// 3. Assert the grouped alert entry is rendered.
		const alertItem = page.getByRole("button").filter({ hasText: /Python HCMC/ });
		await expect(alertItem).toBeVisible({ timeout: 15_000 });
		await expect(page.getByText("+1 new match")).toBeVisible();

		// 4. Click the alert and verify navigation to the saved search snapshot.
		await alertItem.click();
		await page.waitForURL(/\/dashboard\/\d+\/research\/saved-searches\/[0-9a-f-]+\?snapshot=/, {
			timeout: 15_000,
		});
		await expect(page.getByText(/Python HCMC/)).toBeVisible({ timeout: 15_000 });
	});
});
