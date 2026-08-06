import crypto from "node:crypto";
import { expect, test } from "@playwright/test";
import { acquireTestToken, authHeaders, BACKEND_URL } from "../helpers/api/auth";
import { createThread } from "../helpers/api/chat";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * E2E smoke test for run citations in the chat UI.
 *
 * Seeds a thread with an assistant message containing a [citation:run_<uuid>]
 * marker, mocks the run-detail endpoint, and verifies the chip opens the
 * right-panel run detail.
 */

test.describe("Chat run citation", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E Run Citation ${Date.now()}`);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("renders a run citation chip and opens the run detail panel", async ({ page, request }) => {
		const runUuid = crypto.randomUUID();
		const runHandle = `run_${runUuid}`;

		const thread = await createThread(request, ownerToken, workspaceId, "Run citation chat");

		// Seed an assistant message with a run citation marker.
		const content = [
			{
				type: "text",
				text: `According to the scraper, the widget is in stock. [citation:${runHandle}]`,
			},
		];
		const messageRes = await request.post(`${BACKEND_URL}/api/v1/threads/${thread.id}/messages`, {
			headers: authHeaders(ownerToken),
			data: { role: "assistant", content },
		});
		if (!messageRes.ok()) {
			throw new Error(`append message failed: ${await messageRes.text()}`);
		}

		// Mock the run detail endpoint used by the citation panel.
		await page.route(
			new RegExp(`.*/api/v1/workspaces/${workspaceId}/scrapers/runs/${runUuid}$`),
			async (route) => {
				await route.fulfill({
					status: 200,
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						id: runUuid,
						capability: "walmart.scrape",
						origin: "agent",
						status: "success",
						item_count: 1,
						char_count: 120,
						duration_ms: 1200,
						cost_micros: 5000,
						error: null,
						created_at: new Date().toISOString(),
						thread_id: null,
						input: { keyword: "tent", max_items: 5 },
						output_text: '{"title":"Ozark Trail 4-Person Dome Tent"}',
						progress: [{ phase: "search", current: 1, total: 1 }],
					}),
				});
			}
		);

		await page.goto(`/dashboard/${workspaceId}/new-chat/${thread.id}`);

		const sourceChip = page.getByRole("button", { name: /View scraper run/ });
		await expect(sourceChip).toBeVisible({ timeout: 15_000 });
		await expect(sourceChip).toContainText("Source");

		await sourceChip.click();

		await expect(page.getByRole("heading", { name: "Scraper run" })).toBeVisible({
			timeout: 15_000,
		});
		await expect(page.getByText("Input")).toBeVisible();
		await expect(page.getByText("Output")).toBeVisible();
		await expect(page.getByText("Ozark Trail 4-Person Dome Tent")).toBeVisible();
	});
});
