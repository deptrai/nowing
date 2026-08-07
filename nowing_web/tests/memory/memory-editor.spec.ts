import type { APIRequestContext } from "@playwright/test";
import { expect, test } from "../fixtures";
import { authHeaders, BACKEND_URL } from "../helpers/api/auth";

const TEAM_MEMORY =
	"## Facts\n- 2026-07-25: Seeded team memory for the Story 3.8 browser journey.\n";
const USER_MEMORY =
	"## Facts\n- 2026-07-25: Seeded personal memory for the Story 3.8 browser journey.\n";

async function putMemory(
	request: APIRequestContext,
	token: string,
	path: string,
	memory_md: string
) {
	const response = await request.put(`${BACKEND_URL}${path}`, {
		headers: authHeaders(token),
		data: { memory_md },
		timeout: 60_000,
	});
	expect(response.status(), `PUT ${path} should succeed`).toBe(200);
}

async function resetMemory(request: APIRequestContext, token: string, path: string) {
	const response = await request.post(`${BACKEND_URL}${path}`, {
		headers: authHeaders(token),
		timeout: 60_000,
	});
	expect([200, 204], `POST ${path} should succeed`).toContain(response.status());
}

test.describe("Memory editor (Story 3.8)", () => {
	test.beforeEach(async ({ request, apiToken, workspace }) => {
		await Promise.all([
			putMemory(request, apiToken, `/api/v1/workspaces/${workspace.id}/memory`, TEAM_MEMORY),
			putMemory(request, apiToken, "/api/v1/users/me/memory", USER_MEMORY),
		]);
	});

	test.afterEach(async ({ request, apiToken, workspace }) => {
		await Promise.all([
			resetMemory(request, apiToken, `/api/v1/workspaces/${workspace.id}/memory/reset`),
			resetMemory(request, apiToken, "/api/v1/users/me/memory/reset"),
		]);
	});

	test("[P0] should open TEAM_MEMORY.md editor from sidebar", async ({ page, workspace }) => {
		test.setTimeout(120_000);
		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});

		const teamMemory = page
			.locator('div[role="button"]', { hasText: "TEAM_MEMORY.md" })
			.filter({ visible: true })
			.first();
		await expect(teamMemory).toBeVisible({ timeout: 60_000 });
		await teamMemory.click();

		await expect(page.locator("p", { hasText: "TEAM_MEMORY.md" }).filter({ visible: true }).first()).toBeVisible({
			timeout: 20_000,
		});
		// Memory view mode falls back to raw markdown editor, so assert text rather
		// than a semantic Plate heading.
		await expect(page.getByText("Facts").filter({ visible: true }).first()).toBeVisible({
			timeout: 30_000,
		});
		await expect(page.getByText(/Seeded team memory/).filter({ visible: true }).first()).toBeVisible({
			timeout: 30_000,
		});
	});

	test("[P0] should open MEMORY.md editor from sidebar", async ({ page, workspace }) => {
		test.setTimeout(120_000);
		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});

		const userMemory = page
			.locator('div[role="button"]', { hasText: "MEMORY.md" })
			.filter({ visible: true })
			.first();
		await expect(userMemory).toBeVisible({ timeout: 60_000 });
		await userMemory.click();

		await expect(page.locator("p", { hasText: "MEMORY.md" }).filter({ visible: true }).first()).toBeVisible({
			timeout: 20_000,
		});
		await expect(page.getByText("Facts").filter({ visible: true }).first()).toBeVisible({
			timeout: 30_000,
		});
		await expect(page.getByText(/Seeded personal memory/).filter({ visible: true }).first()).toBeVisible({
			timeout: 30_000,
		});
	});

	test("[P1] should save team memory markdown and reflect in structured search", async ({
		page,
		workspace,
		request,
		apiToken,
	}) => {
		test.setTimeout(120_000);
		await resetMemory(request, apiToken, `/api/v1/workspaces/${workspace.id}/memory/reset`);
		await page.goto(`/dashboard/${workspace.id}/new-chat`, {
			waitUntil: "domcontentloaded",
		});
		const teamMemory = page
			.locator('div[role="button"]', { hasText: "TEAM_MEMORY.md" })
			.filter({ visible: true })
			.first();
		await expect(teamMemory).toBeVisible({ timeout: 60_000 });
		await teamMemory.click();

		await expect(page.locator("p", { hasText: "TEAM_MEMORY.md" }).filter({ visible: true }).first()).toBeVisible({
			timeout: 20_000,
		});

		// Let the animated right panel settle before interacting with its header.
		await page.waitForTimeout(1000);

		await page
			.getByRole("button", { name: "Edit document" })
			.filter({ visible: true })
			.first()
			.click({ force: true });

		const canary = `E2E canary ${Date.now()}: structured memory bridge works.`;
		const editor = page.locator(".monaco-editor").first();
		await expect(editor).toBeVisible({ timeout: 20_000 });
		const markdown = `## Facts\n- 2026-07-25: ${canary}\n`;
		await page.waitForFunction(() => {
			const w = window as unknown as { monaco?: { editor: { getModels: () => unknown[] } } };
			return w.monaco !== undefined && w.monaco.editor.getModels().length > 0;
		});
		await page.evaluate((text) => {
			const w = window as unknown as { monaco: { editor: { getModels: () => Array<{ setValue: (value: string) => void }> } } };
			w.monaco.editor.getModels()[0].setValue(text);
		}, markdown);

		// Wait a beat for the Monaco change callback to mark the document dirty.
		await page.waitForTimeout(500);
		await page
			.getByRole("button", { name: "Save", exact: true })
			.filter({ visible: true })
			.first()
			.click({ force: true });

		await expect(page.getByText(canary)).toBeVisible({ timeout: 20_000 });

		const searchResponse = await request.post(
			`${BACKEND_URL}/api/v1/workspaces/${workspace.id}/memories/search`,
			{
				headers: authHeaders(apiToken),
				data: { query: canary, top_k: 5 },
			}
		);
		expect(searchResponse.status()).toBe(200);
		const body = (await searchResponse.json()) as {
			items: Array<{ content?: string }>;
		};
		expect(body.items.some((item) => item.content?.includes(canary))).toBe(true);
	});
});
