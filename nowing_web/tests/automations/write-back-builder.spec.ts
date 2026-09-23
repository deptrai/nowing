import { expect, test } from "../fixtures";
import { BACKEND_URL } from "../helpers/api/auth";

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

/**
 * Red-phase ATDD tests for Story 6.4: Direct Write-Back Actions.
 */

test.describe("Write-back automation builder (Story 6.4)", () => {
	test("[P0] user can add a write-back Notion step", async ({ page, workspace }) => {
		await markWorkspaceSetupReady(page, workspace.id);
		await page.goto(`/dashboard/${workspace.id}/automations/new`);
		await expect(page.getByRole("heading", { name: "New automation" })).toBeVisible();

		// Add a task and change its action to Notion write-back.
		await page.getByRole("button", { name: "Add task" }).click();
		const taskSection = page.getByTestId("task-item-0");
		await taskSection.getByRole("combobox", { name: /action/i }).click();
		await page.getByRole("option", { name: /write back to notion/i }).click();

		// Provider-specific fields should appear.
		await taskSection.getByLabel(/title/i).fill("Weekly digest");
		await taskSection.getByLabel(/content/i).fill("Summary from previous step");

		await page.getByRole("button", { name: "Create automation" }).click();
		await page.waitForURL(`/dashboard/${workspace.id}/automations/*`);
	});

	test("[P0] user can add a write-back Slack step", async ({ page, workspace }) => {
		await markWorkspaceSetupReady(page, workspace.id);
		await page.goto(`/dashboard/${workspace.id}/automations/new`);
		await page.getByRole("button", { name: "Add task" }).click();

		const taskSection = page.getByTestId("task-item-0");
		await taskSection.getByRole("combobox", { name: /action/i }).click();
		await page.getByRole("option", { name: /write back to slack/i }).click();

		await taskSection.getByLabel(/channel/i).fill("#daily-digest");
		await taskSection.getByLabel(/text/i).fill("{{ steps.summarize.final_message }}");

		await page.getByRole("button", { name: "Create automation" }).click();
		await page.waitForURL(`/dashboard/${workspace.id}/automations/*`);
	});

	test("[P1] builder validates write-back params per provider", async ({ page, workspace }) => {
		await markWorkspaceSetupReady(page, workspace.id);
		await page.goto(`/dashboard/${workspace.id}/automations/new`);
		await page.getByRole("button", { name: "Add task" }).click();

		const taskSection = page.getByTestId("task-item-0");
		await taskSection.getByRole("combobox", { name: /action/i }).click();
		await page.getByRole("option", { name: /write back to jira/i }).click();

		// Touch and clear the required Jira fields so the form validates them.
		const projectKey = taskSection.getByLabel(/project key/i);
		await projectKey.fill("KEY");
		await projectKey.clear();
		await projectKey.blur();

		const summary = taskSection.getByLabel(/summary/i);
		await summary.fill("Summary");
		await summary.clear();
		await summary.blur();

		await expect(page.getByText(/project key is required/i)).toBeVisible();
		await expect(page.getByText(/summary is required/i)).toBeVisible();
	});

	test("[P0] automation with write-back step persists action type", async ({
		page,
		workspace,
		request,
		apiToken,
	}) => {
		await markWorkspaceSetupReady(page, workspace.id);
		await page.goto(`/dashboard/${workspace.id}/automations/new`);
		await page.getByLabel(/name/i).fill("Notion write-back test");

		await page.getByRole("button", { name: "Add task" }).click();
		const taskSection = page.getByTestId("task-item-0");
		await taskSection.getByRole("combobox", { name: /action/i }).click();
		await page.getByRole("option", { name: /write back to notion/i }).click();
		await taskSection.getByLabel(/title/i).fill("Digest");
		await taskSection.getByLabel(/content/i).fill("Body");

		await page.getByRole("button", { name: "Create automation" }).click();
		await page.waitForURL(`/dashboard/${workspace.id}/automations/*`);

		const automationId = page.url().split("/").pop();
		const response = await request.get(`${BACKEND_URL}/api/v1/automations/${automationId}`, {
			headers: { Authorization: `Bearer ${apiToken}` },
		});
		expect(response.status()).toBe(200);
		const body = await response.json();
		expect(body.definition.plan[0].action).toBe("write_back_notion");
	});
});
