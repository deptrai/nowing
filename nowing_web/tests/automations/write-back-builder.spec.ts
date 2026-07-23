import { expect, test } from "../fixtures";

/**
 * Red-phase ATDD tests for Story 6.4: Direct Write-Back Actions.
 *
 * These tests describe the expected builder UX for adding write-back steps
 * to an automation. They are skipped until the action selector and provider
 * parameter fields are implemented in the automation builder.
 */

test.describe("Write-back automation builder (Story 6.4)", () => {
	test("[P0] user can add a write-back Notion step", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/automations/new`);
		await expect(page.getByRole("heading", { name: "New automation" })).toBeVisible();

		// Add a task and change its action to Notion write-back.
		await page.getByRole("button", { name: "Add task" }).click();
		const taskSection = page.getByText("Task 1").locator("..");
		await taskSection.getByRole("combobox", { name: /action/i }).click();
		await page.getByRole("option", { name: /write back to notion/i }).click();

		// Provider-specific fields should appear.
		await taskSection.getByLabel(/title/i).fill("Weekly digest");
		await taskSection.getByLabel(/content/i).fill("Summary from previous step");

		await page.getByRole("button", { name: "Create automation" }).click();
		await page.waitForURL(`/dashboard/${workspace.id}/automations/*`);
	});

	test("[P0] user can add a write-back Slack step", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/automations/new`);
		await page.getByRole("button", { name: "Add task" }).click();

		const taskSection = page.getByText("Task 1").locator("..");
		await taskSection.getByRole("combobox", { name: /action/i }).click();
		await page.getByRole("option", { name: /write back to slack/i }).click();

		await taskSection.getByLabel(/channel/i).fill("#daily-digest");
		await taskSection.getByLabel(/text/i).fill("{{ steps.summarize.final_message }}");

		await page.getByRole("button", { name: "Create automation" }).click();
		await page.waitForURL(`/dashboard/${workspace.id}/automations/*`);
	});

	test("[P1] builder validates write-back params per provider", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/automations/new`);
		await page.getByRole("button", { name: "Add task" }).click();

		const taskSection = page.getByText("Task 1").locator("..");
		await taskSection.getByRole("combobox", { name: /action/i }).click();
		await page.getByRole("option", { name: /write back to jira/i }).click();

		// Try to submit without provider-required fields.
		await page.getByRole("button", { name: "Create automation" }).click();
		await expect(page.getByText(/project key is required/i)).toBeVisible();
		await expect(page.getByText(/summary is required/i)).toBeVisible();
	});

	test(
		"[P0] automation with write-back step persists action type",
		async ({ page, workspace, request, apiToken }) => {
			await page.goto(`/dashboard/${workspace.id}/automations/new`);
			await page.getByLabel(/name/i).fill("Notion write-back test");

			await page.getByRole("button", { name: "Add task" }).click();
			const taskSection = page.getByText("Task 1").locator("..");
			await taskSection.getByRole("combobox", { name: /action/i }).click();
			await page.getByRole("option", { name: /write back to notion/i }).click();
			await taskSection.getByLabel(/title/i).fill("Digest");
			await taskSection.getByLabel(/content/i).fill("Body");

			await page.getByRole("button", { name: "Create automation" }).click();
			await page.waitForURL(`/dashboard/${workspace.id}/automations/*`);

			const automationId = page.url().split("/").pop();
			const response = await request.get(`/api/v1/automations/${automationId}`, {
				headers: { Authorization: `Bearer ${apiToken}` },
			});
			expect(response.status()).toBe(200);
			const body = await response.json();
			expect(body.definition.plan[0].action).toBe("write_back_notion");
		}
	);
});
