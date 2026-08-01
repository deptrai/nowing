import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * Red-phase E2E tests for Story 8.3: Usage & Credit Dashboard.
 *
 * These tests assert the expected UI behavior for the `/dashboard/{workspaceId}/usage`
 * page. They are skipped until the frontend page and components are implemented.
 */

test.describe("Usage & Credit Dashboard", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`ATDD Usage Dashboard ${Date.now()}`
		);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test.skip("owner can navigate to usage page from sidebar", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/new-chat`);

		const usageNav = page.getByRole("link", { name: /usage/i });
		await expect(usageNav).toBeVisible();
		await usageNav.click();

		await page.waitForURL(`/dashboard/${workspaceId}/usage`);
		await expect(page.getByRole("heading", { name: /usage|credit/i, level: 1 })).toBeVisible();
	});

	test.skip("dashboard displays balance and reserved credits", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/usage`);

		await expect(page.getByText(/current balance/i)).toBeVisible();
		await expect(page.getByText(/reserved/i)).toBeVisible();
	});

	test.skip("dashboard displays total tokens and total cost", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/usage`);

		await expect(page.getByText(/total tokens/i)).toBeVisible();
		await expect(page.getByText(/total cost/i)).toBeVisible();
	});

	test.skip("dashboard has usage breakdown by type, model, and provider", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/usage`);

		await expect(page.getByText(/by usage type/i)).toBeVisible();
		await expect(page.getByText(/by model/i)).toBeVisible();
		await expect(page.getByText(/by provider/i)).toBeVisible();
	});

	test.skip("dashboard has a time-series usage chart", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/usage`);

		// Chart container should be present; exact SVG/Canvas structure depends on recharts.
		await expect(page.locator("[data-testid='usage-chart']")).toBeVisible();
	});

	test.skip("dashboard displays transaction history", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/usage`);

		await expect(page.getByText(/transaction history/i)).toBeVisible();
		const rows = page.locator("[data-testid='transaction-row']");
		await expect(rows).toHaveCount(0);
	});

	test.skip("dashboard supports date range presets", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/usage`);

		const last7Days = page.getByRole("button", { name: /last 7 days/i });
		const last30Days = page.getByRole("button", { name: /last 30 days/i });
		const last90Days = page.getByRole("button", { name: /last 90 days/i });

		await expect(last7Days).toBeVisible();
		await expect(last30Days).toBeVisible();
		await expect(last90Days).toBeVisible();

		await last7Days.click();
		await expect(page.getByText(/last 7 days/i)).toBeVisible();
	});

	test.skip("dashboard shows empty state when no usage exists", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/usage`);

		await expect(page.getByText(/no usage yet/i)).toBeVisible();
		await expect(page.getByText(/start a chat to see usage/i)).toBeVisible();
	});
});
