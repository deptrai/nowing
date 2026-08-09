import { expect, test } from "../fixtures";

/**
 * Story 7.4: Dedicated connectors layout navigation and rendering.
 *
 * Verifies:
 *   - The /dashboard/{workspace_id}/connectors route renders the rail and overview.
 *   - Clicking a connector card in the overview opens the detail pane.
 */

test.describe("Connectors page", () => {
	test("rail and overview render, and clicking a card opens the detail pane", async ({
		page,
		workspace,
	}) => {
		await page.goto(`/dashboard/${workspace.id}/connectors`);

		// Rail: wait for the "Connected integrations" header.
		await expect(page.getByText("Connected integrations").first()).toBeVisible({ timeout: 30_000 });

		// Overview: search input and at least one connector card.
		await expect(page.getByPlaceholder("Search integrations…")).toBeVisible();
		await expect(page.getByText("Notion").first()).toBeVisible();

		// Click a connector card's Connect button.
		const notionCard = page.locator("div", { hasText: "Notion" }).first();
		await notionCard.getByRole("button", { name: "Connect" }).click();

		// Detail pane should open with a back button and connector title.
		await expect(page.getByRole("button", { name: "Back to catalog" })).toBeVisible();
		await expect(page.getByText("Notion").nth(1)).toBeVisible();
	});
});
