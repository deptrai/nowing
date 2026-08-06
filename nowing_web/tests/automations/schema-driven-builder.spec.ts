import { expect, test } from "../fixtures";

/**
 * Smoke test for Story 6.7: schema-driven action params in the automation
 * builder. Verifies the action catalog loads and a selected action renders
 * its JSON Schema via SchemaForm.
 */

test.describe("Schema-driven builder (Story 6.7)", () => {
	test("loads action catalog and renders schema fields", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/automations/new`);
		await expect(page.getByRole("heading", { name: "New automation" })).toBeVisible();

		// The initial task is an agent task; open its action select.
		const taskSection = page.getByText("Task 1").locator("..");
		await taskSection.getByRole("combobox", { name: /action/i }).click();

		// The catalog should include all registered write-back actions plus agent_task.
		await expect(page.getByRole("option", { name: /write back to notion/i })).toBeVisible();
		await page.getByRole("option", { name: /write back to notion/i }).click();

		// SchemaForm should render fields derived from the Notion params schema.
		await expect(page.getByRole("textbox", { name: /title/i })).toBeVisible();
	});
});
