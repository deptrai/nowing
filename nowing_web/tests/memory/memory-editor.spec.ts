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
	});
	expect(response.status(), `PUT ${path} should succeed`).toBe(200);
}

async function resetMemory(request: APIRequestContext, token: string, path: string) {
	const response = await request.post(`${BACKEND_URL}${path}`, {
		headers: authHeaders(token),
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
		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		const teamMemory = page.getByRole("button", {
			name: "TEAM_MEMORY.md Document actions for TEAM_MEMORY.md",
		});
		await expect(teamMemory).toBeVisible({ timeout: 60_000 });
		await teamMemory.click();

		await expect(page.getByText("TEAM_MEMORY.md", { exact: true }).last()).toBeVisible({
			timeout: 10_000,
		});
		await expect(page.getByRole("heading", { name: "Facts", exact: true })).toBeVisible({
			timeout: 10_000,
		});
		await expect(page.getByText(/Seeded team memory/)).toBeVisible();
	});

	test("[P0] should open MEMORY.md editor from sidebar", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		const userMemory = page.getByRole("button", {
			name: "MEMORY.md Document actions for MEMORY.md",
		});
		await expect(userMemory).toBeVisible({ timeout: 60_000 });
		await userMemory.click();

		await expect(page.getByText("MEMORY.md", { exact: true }).last()).toBeVisible({
			timeout: 10_000,
		});
		await expect(page.getByRole("heading", { name: "Facts", exact: true })).toBeVisible({
			timeout: 10_000,
		});
		await expect(page.getByText(/Seeded personal memory/)).toBeVisible();
	});

	test("[P1] should save team memory markdown and reflect in structured search", async ({
		page,
		workspace,
		request,
		apiToken,
	}) => {
		await resetMemory(request, apiToken, `/api/v1/workspaces/${workspace.id}/memory/reset`);
		await page.goto(`/dashboard/${workspace.id}/new-chat`);
		const teamMemory = page.getByRole("button", {
			name: "TEAM_MEMORY.md Document actions for TEAM_MEMORY.md",
		});
		await expect(teamMemory).toBeVisible({ timeout: 60_000 });
		await teamMemory.click();
		await expect(page.getByText("TEAM_MEMORY.md", { exact: true }).last()).toBeVisible({
			timeout: 10_000,
		});

		await page.getByRole("button", { name: "Edit document" }).click();
		const canary = `E2E canary ${Date.now()}: structured memory bridge works.`;
		const editor = page.locator(".monaco-editor").last();
		await editor.click();
		await page.keyboard.insertText(`## Facts\n- 2026-07-25: ${canary}\n`);
		await page.getByRole("button", { name: "Save" }).click();

		await expect(page.getByText(canary)).toBeVisible({ timeout: 10_000 });

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
