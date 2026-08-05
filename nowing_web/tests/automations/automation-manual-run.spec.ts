import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createAutomation, deleteAutomation, runAutomation } from "../helpers/api/automations";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

test.describe("Automation manual run — web handles new backend run", () => {
	let workspaceId: number;
	let automationId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E Manual Run ${Date.now()}`);
		workspaceId = workspace.id;
		const automation = await createAutomation(
			request,
			ownerToken,
			workspaceId,
			"E2E manual-run automation"
		);
		automationId = automation.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteAutomation(request, ownerToken, automationId);
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("should display a PENDING run after manual run without crashing", async ({
		request,
		page,
	}) => {
		// Trigger the new Story 7.7 endpoint directly; the web UI will
		// receive it via Zero sync on the automation detail page.
		const run = await runAutomation(request, ownerToken, automationId);
		expect(run.status).toBe("pending");

		await page.goto(`/dashboard/${workspaceId}/automations/${automationId}`);

		// Wait for the detail page header and runs section to render.
		await expect(page.getByRole("heading", { name: /automation/i })).toBeVisible();
		await expect(page.getByText("Recent runs")).toBeVisible();

		// The PENDING run should appear in the list.
		await expect(page.getByText("Pending").first()).toBeVisible();

		// No Next.js error overlay.
		await expect(page.getByText(/application error|failed to compile/i)).toHaveCount(0);
	});
});
