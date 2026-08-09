import { expect, test } from "../fixtures";

/**
 * Smoke test for the anti-bot escalations admin page.
 * Verifies the route renders for an authenticated workspace user.
 */
test.describe("Anti-bot escalations smoke", () => {
	test("admin page loads without access-denied message", async ({ page }) => {
		await page.goto("/admin/anti-bot-escalations");
		await expect(
			page.getByRole("heading", { name: /Anti-bot escalations/i })
		).toBeVisible({ timeout: 30_000 });
		await expect(
			page.getByText("You must be a workspace Owner, Editor, or superuser to view this page.")
		).not.toBeVisible();
	});
});
