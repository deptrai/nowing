import { expect, test } from "../fixtures";

/**
 * Authenticated smoke tests for workspace-scoped pages that previously had no
 * spec coverage: logs, team, governance, CRM, artifacts, playbooks.
 *
 * Each test gets a fresh workspace from the `workspace` fixture (created via
 * API, deleted on teardown) and asserts the route renders its landmark content
 * instead of an error boundary or a redirect to /login.
 *
 * The seeded auth state captures `nowing-locale` from the machine that ran
 * auth.setup (Vietnam timezones → "vi"); the init script below pins English
 * before app code reads localStorage so assertions stay locale-independent.
 */
test.describe("Workspace pages", () => {
	test.use({ locale: "en-US", timezoneId: "America/New_York" });

	test.beforeEach(async ({ page }) => {
		await page.addInitScript(() => {
			localStorage.setItem("nowing-locale", "en");
		});
	});

	test("logs page renders task log console", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/logs`);
		await expect(page.getByText("Task Logs").first()).toBeVisible();
	});

	test("team page renders members list", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/team`);
		await expect(page.getByText("Members").first()).toBeVisible();
	});

	test("governance page renders console", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/governance`);
		await expect(page.getByText("Governance").first()).toBeVisible();
	});

	test("crm page renders pipeline", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/crm`);
		await expect(page.getByText("CRM & Sales Pipeline").first()).toBeVisible();
	});

	test("artifacts page renders empty state", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/artifacts`);
		await expect(page.getByText(/artifacts/i).first()).toBeVisible();
	});

	test("playbooks page renders marketplace", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/playbooks`);
		await expect(page.getByText(/playbook/i).first()).toBeVisible();
	});
});
