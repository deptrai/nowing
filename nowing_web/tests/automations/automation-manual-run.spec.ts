import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createAutomation, deleteAutomation, runAutomation } from "../helpers/api/automations";
import {
	createWorkspace,
	deleteWorkspace,
	setWorkspaceModelRoles,
} from "../helpers/api/workspaces";

async function markWorkspaceSetupReady(
	page: import("@playwright/test").Page,
	workspaceId: number
) {
	await page.route(`**/api/v1/workspaces/${workspaceId}/llm-setup-status`, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({
				status: "ready",
				source: "global_config",
				can_configure: true,
				stage: "ready",
			}),
		});
	});
}

test.describe("Automation manual run — web handles new backend run", () => {
	let workspaceId: number;
	let automationId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E Manual Run ${Date.now()}`);
		workspaceId = workspace.id;
		// Automations require explicit (billable) model selections.
		await setWorkspaceModelRoles(request, ownerToken, workspaceId, {
			chat_model_id: -1,
			image_gen_model_id: -101,
			vision_model_id: -1,
		});
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

		// Avoid /onboard redirect for this freshly-created workspace so the
		// automation detail page can render immediately.
		await markWorkspaceSetupReady(page, workspaceId);

		await page.goto(`/dashboard/${workspaceId}/automations/${automationId}`);

		// Wait for the detail page header and runs section to render.
		await expect(page.getByTestId("automation-detail-name")).toBeVisible();
		await expect(page.getByTestId("automation-recent-runs-heading")).toBeVisible();

		// The PENDING run should appear in the list.
		await expect(page.getByText("Pending").first()).toBeVisible();

		// No Next.js error overlay.
		await expect(page.getByText(/application error|failed to compile/i)).toHaveCount(0);
	});
});
