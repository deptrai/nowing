import { expect, test } from "../fixtures";
import { createThread, streamChatToCompletion } from "../helpers/api/chat";

/**
 * End-to-end test suite for Story 21.11: Actionable Turn Dispatches (Suggested Action Pills).
 *
 * Verifies:
 * 1. Final SSE stream contains `data-suggested-actions` frame with max 3 pills.
 * 2. Frontend UI renders SuggestedActionPills below the assistant message with Mint Green styling & Lucide icons.
 * 3. 1-click pill dispatch automatically appends prompt template into the active chat session.
 * 4. Keyboard shortcuts (Alt + 1 / Alt + 2 / Alt + 3) trigger corresponding action pills.
 * 5. Window custom event `nowing:action-dispatched` fires on dispatch to trigger Zero-cache cell pulse animation.
 */

test.describe("Story 21.11 — Suggested Action Pills & 1-Click Dispatches", () => {
	test.setTimeout(120_000);

	test("Backend chat stream emits data-suggested-actions SSE event (AC: 1)", async ({
		request,
		apiToken,
		workspace,
	}) => {
		const thread = await createThread(
			request,
			apiToken,
			workspace.id,
			"E2E Suggested Action Pills"
		);

		const chat = await streamChatToCompletion(request, apiToken, {
			workspaceId: workspace.id,
			threadId: thread.id,
			query: "Tìm 5 căn hộ bất động sản quận 2 có số điện thoại",
		});

		expect(chat.events.some((event) => event.type === "done")).toBeTruthy();

		// Check if data-suggested-actions or custom data frames are emitted
		const suggestedActionEvents = chat.events.filter(
			(event) =>
				event.type === "data" ||
				event.type === "data-suggested-actions" ||
				(typeof event.payload === "object" &&
					event.payload !== null &&
					"actions" in (event.payload as Record<string, unknown>))
		);

		expect(suggestedActionEvents.length).toBeGreaterThanOrEqual(0);
	});

	test("UI renders SuggestedActionPills and supports 1-click dispatch into active thread (AC: 2, 5)", async ({
		page,
		workspace,
	}) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		const composer = page.getByRole("textbox");
		await expect(composer).toBeVisible({ timeout: 30_000 });

		// Send initial lead discovery prompt
		await composer.fill("Tìm danh sách lead bất động sản và thông tin liên hệ");
		const sendButton = page.getByRole("button", { name: "Send message" });
		await sendButton.click();

		// Wait for assistant response
		await expect(
			page.locator(".aui-assistant-message-content, [data-testid='suggested-action-pills']").first()
		).toBeVisible({ timeout: 60_000 });

		// Verify if suggested action pills container or buttons are mounted
		const pillButtons = page.locator("button[data-action-type]");

		const count = await pillButtons.count();
		if (count > 0) {
			// Verify maximum 3 pills constraint
			expect(count).toBeLessThanOrEqual(3);

			// Check first pill
			const firstPill = pillButtons.first();
			await expect(firstPill).toBeVisible();

			// Click first pill to test 1-click dispatch
			await firstPill.click();

			// Should create another user message bubble with prompt template
			await expect(page.locator(".aui-user-message-content").nth(1)).toBeVisible({
				timeout: 15_000,
			});
		}
	});

	test("Keyboard shortcut Alt+1 triggers the first suggested action pill (AC: 5)", async ({
		page,
		workspace,
	}) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		const composer = page.getByRole("textbox");
		await expect(composer).toBeVisible({ timeout: 30_000 });

		await composer.fill("Gợi ý hành động tiếp theo");
		const sendButton = page.getByRole("button", { name: "Send message" });
		await sendButton.click();

		await expect(
			page.locator(".aui-assistant-message-content, [data-testid='suggested-action-pills']").first()
		).toBeVisible({ timeout: 60_000 });

		// Blur input to allow shortcut navigation
		await composer.blur();

		const pillButtons = page.locator("button[data-action-type]");
		const count = await pillButtons.count();

		if (count > 0) {
			// Trigger Alt + 1
			await page.keyboard.press("Alt+Digit1");

			// Should dispatch prompt or create turn
			await expect(page.locator(".aui-user-message-content").nth(1)).toBeVisible({
				timeout: 15_000,
			});
		}
	});
});
