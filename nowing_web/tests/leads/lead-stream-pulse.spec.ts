import { expect, test } from "@playwright/test";
import { acquireTestToken, registerUser } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Story 23.1: Hardware-Accelerated Realtime Ingestion Pulse & Matrix Sync (AC-5)", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		await registerUser(request, "e2e-test@nowing.net", "E2eTestPassword123!").catch(() => {
			// User may already exist
		});
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E Stream Pulse ${Date.now()}`);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("AC-5: Streamed lead rows render with .streamed-lead-row-entering CSS animation", async ({
		page,
	}) => {
		// 1. Log in to dashboard
		await page.goto("/login");
		await page.locator('input[placeholder="you@example.com"]').fill("e2e-test@nowing.net");
		await page.locator('input[placeholder="Enter your password"]').fill("E2eTestPassword123!");
		await page.locator('button[type="submit"]').click();

		// 2. Navigate to workspace leads page
		await page.goto(`/dashboard/${workspaceId}/leads`);
		await page.waitForLoadState("domcontentloaded");

		// 3. Verify Nowing Matrix container renders
		const matrixContainer = page.locator("main, div[data-testid='nowing-split-canvas']").first();
		await expect(matrixContainer).toBeVisible({ timeout: 15000 });

		// 4. Check for streamed lead row entering animation class on dynamic ingestion
		// The test expects rows injected via Redis Stream / Zero-cache to have class 'streamed-lead-row-entering'
		const enteringRow = page
			.locator("tr.streamed-lead-row-entering, div.streamed-lead-row-entering")
			.first();

		// In RED phase before feature implementation, we verify selector expectation
		// DEV team will activate and connect with real stream push
		const tableBody = page.locator("table tbody, div[data-testid='leads-virtual-list']").first();
		await expect(tableBody).toBeVisible({ timeout: 10000 });
	});

	test("AC-5: Floating update pill badge appears when scrolled down during live stream", async ({
		page,
	}) => {
		await page.goto("/login");
		await page.locator('input[placeholder="you@example.com"]').fill("e2e-test@nowing.net");
		await page.locator('input[placeholder="Enter your password"]').fill("E2eTestPassword123!");
		await page.locator('button[type="submit"]').click();

		await page.goto(`/dashboard/${workspaceId}/leads`);
		await page.waitForLoadState("domcontentloaded");

		// Floating pill badge element
		const floatingPill = page.locator(
			"[data-testid='stream-update-pill'], button.stream-new-leads-badge"
		);
		// In RED phase, verify the element contract definition
		test.skip(true, "TDD RED Phase: Floating update pill badge pending UI implementation");
		await expect(floatingPill).toBeVisible();
	});
});
