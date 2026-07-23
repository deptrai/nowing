import { expect, test } from "../fixtures";

/**
 * Red-phase E2E tests for the legacy memory editor bridge (Story 3.8).
 *
 * These tests assert the existing MEMORY.md / TEAM_MEMORY.md sidebar entries
 * still open the editor panel and can load/save through the legacy endpoints
 * once those endpoints are backed by the unified `Memory` table.
 */

test.describe("Memory editor (ATDD red phase)", () => {
	test.skip("[P0] should open TEAM_MEMORY.md editor from sidebar", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}`);

		// Wait for the sidebar to populate.
		await expect(page.getByRole("complementary").first()).toBeVisible({ timeout: 60_000 });

		// Click the virtual team memory document.
		await page.getByText("TEAM_MEMORY.md").click();

		// The editor panel should appear with the document title.
		await expect(page.getByRole("heading", { name: "TEAM_MEMORY.md" })).toBeVisible({ timeout: 10_000 });

		// The legacy GET endpoint should eventually populate the editor.
		await expect(page.getByText("## Facts").or(page.getByText("## Memory")).first()).toBeVisible({ timeout: 10_000 });
	});

	test.skip("[P0] should open MEMORY.md editor from sidebar", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}`);
		await expect(page.getByRole("complementary").first()).toBeVisible({ timeout: 60_000 });

		await page.getByText("MEMORY.md").click();

		await expect(page.getByRole("heading", { name: "MEMORY.md" })).toBeVisible({ timeout: 10_000 });
		await expect(page.getByText("## Facts").or(page.getByText("## Memory")).first()).toBeVisible({ timeout: 10_000 });
	});

	test.skip("[P1] should save team memory markdown and reflect in structured search", async ({ page, workspace, request, apiToken }) => {
		await page.goto(`/dashboard/${workspace.id}`);
		await expect(page.getByRole("complementary").first()).toBeVisible({ timeout: 60_000 });

		await page.getByText("TEAM_MEMORY.md").click();
		await expect(page.getByRole("heading", { name: "TEAM_MEMORY.md" })).toBeVisible({ timeout: 10_000 });

		// Place a unique canary string into the markdown editor.
		const canary = `E2E canary ${Date.now()}: structured memory bridge works.`;
		// The editor is a contenteditable or textarea rendered by SourceCodeEditor.
		const editor = page.locator("[data-slate-editor]").or(page.locator("textarea")).first();
		await editor.fill(`## Facts\n- 2026-07-22: ${canary}\n`);

		// Click the Save button in the editor panel header.
		await page.getByRole("button", { name: /save/i }).click();

		// The legacy PUT parses markdown into Memory rows.
		// Verify via the new structured search endpoint.
		const searchResponse = await request.post(
			`${process.env.BACKEND_URL ?? ""}/workspaces/${workspace.id}/memories/search`,
			{
				headers: { Authorization: `Bearer ${apiToken}` },
				data: { query: canary, top_k: 5 },
			}
		);
		expect(searchResponse.status()).toBe(200);
		const body = await searchResponse.json();
		const contents = body.items.map((item: { content?: string }) => item.content);
		expect(contents.some((content: string) => content?.includes(canary))).toBe(true);
	});
});
