import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

test.describe("Story 8.14 — Usage & Credit Dashboard v2", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`ATDD 8.14 Usage Dashboard ${Date.now()}`
		);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("renders per-turn cost and auto-extract budget sections", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/usage`);

		await expect(page.getByRole("heading", { name: /usage|credit/i, level: 1 })).toBeVisible();

		// Story 8.14 — per-turn cost section
		await expect(page.getByText(/per-turn cost/i)).toBeVisible();

		// Story 8.14 — auto-extract budget card
		await expect(page.getByText(/auto-extract budget/i)).toBeVisible();
		await expect(page.getByLabel(/item cap/i)).toBeVisible();
		await expect(page.getByLabel(/spend cap/i)).toBeVisible();
	});

	test("auto-extract budget caps can be saved", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/usage`);

		const itemCap = page.getByLabel(/item cap/i);
		await itemCap.fill("50");

		const spendCap = page.getByLabel(/spend cap/i);
		await spendCap.fill("5.50");

		const saveButton = page.getByRole("button", { name: /save budget/i });
		await saveButton.click();

		await expect(page.getByText(/auto-extract budget saved/i)).toBeVisible();

		// Reload and assert persistence
		await page.reload();
		await expect(itemCap).toHaveValue("50");
		await expect(spendCap).toHaveValue("5.50");
	});

	test("per-turn section shows empty state when no usage", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/usage`);

		await expect(page.getByText(/per-turn cost/i)).toBeVisible();
		await expect(page.getByText(/no per-turn usage data/i)).toBeVisible();
	});
});
