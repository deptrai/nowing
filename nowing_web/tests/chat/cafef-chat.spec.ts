import { expect, test } from "../fixtures";
import { createThread, streamChatToCompletion } from "../helpers/api/chat";

/**
 * End-to-end tests for the CafeF chat subagent.
 *
 * Verifies the web app handles new chat SSE events (tool-input-start for
 * `task`/`cafef_scrape`, tool-output-available, data-terminal-info) without
 * crashing, and that the chat agent can route Vietnamese stock queries to the
 * CafeF subagent.
 *
 * Requires the E2E fake LLM to trigger `task(subagent_type="cafef")` for
 * queries containing "VCB" or "cafef" (see `tests/e2e/fakes/chat_llm.py`).
 */

test.describe("CafeF chat subagent", () => {
	test.setTimeout(120_000);

	test("chat stream completes for a Vietnamese stock query", async ({
		request,
		apiToken,
		workspace,
	}) => {
		const thread = await createThread(request, apiToken, workspace.id, "E2E CafeF chat");
		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: thread.id,
			query: "giá cổ phiếu VCB hôm nay",
		});

		expect(chat.events.some((event) => event.type === "done")).toBeTruthy();
		expect(
			chat.events.some(
				(event) =>
					event.type === "tool-input-start" &&
					typeof event.payload === "object" &&
					event.payload !== null &&
					((event.payload as Record<string, unknown>).toolName === "task" ||
						(event.payload as Record<string, unknown>).toolName === "cafef_scrape")
			),
			"expected a task or cafef_scrape tool call"
		).toBeTruthy();
	});

	test("UI renders assistant response without crashing", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		const composer = page.getByRole("textbox");
		await expect(composer).toBeVisible({ timeout: 30_000 });

		await composer.fill("giá cổ phiếu VCB hôm nay");

		const sendButton = page.getByRole("button", { name: "Send message" });
		await sendButton.click();

		// The stream should produce either a tool-thinking step for CafeF or an
		// assistant response; either way the page must not crash.
		await expect(page.getByText(/Cafef|VCB|fake assistant received/i).first()).toBeVisible({
			timeout: 60_000,
		});

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		await expect(page.getByText(/error report/i)).toHaveCount(0);
	});

	test("redirects to /login when session expires", async ({ page, workspace, context }) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat`);
		await context.clearCookies();
		await page.reload();
		await expect(page).toHaveURL(/\/login/, { timeout: 30_000 });
		await expect(page.getByRole("heading", { name: /sign in|Đăng nhập/i })).toBeVisible();
	});

	test("should load the new-chat page without a white-screen crash", async ({
		page,
		workspace,
	}) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		const composer = page.getByRole("textbox");
		await expect(composer).toBeVisible({ timeout: 30_000 });
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});
});
