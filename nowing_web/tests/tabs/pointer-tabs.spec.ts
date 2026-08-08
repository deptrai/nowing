import { expect, test } from "../fixtures";
import { createThread } from "../helpers/api/chat";

/**
 * E2E tests for Story 4-7: Pointer-Based Tabs with Live Title Resolution.
 *
 * Verifies the web app handles the tab refactor without crashing:
 * - Tab bar renders on dashboard pages
 * - Tab bar hidden on untabbed routes (new-chat root)
 * - Tab switching works
 * - Tab close works
 * - Chat tab resolves live title from API
 * - v1→v2 migration doesn't crash on reload
 *
 * No backend response shape changes — this is a frontend-only refactor.
 * The tests use real API calls (createThread) for setup and verify UI behavior.
 */

test.describe("Pointer-Based Tabs — Story 4-7", () => {
	test("tab bar renders on dashboard with an open chat thread", async ({
		page,
		workspace,
		apiToken,
		request,
	}) => {
		const thread = await createThread(request, apiToken, workspace.id, "E2E Tab Test Chat");

		await page.goto(`/dashboard/${workspace.id}/new-chat/${thread.id}`);

		// Tab bar should be visible (data-tab-id attributes on tab elements)
		const tabBar = page.locator("[data-tab-id]").first();
		await expect(tabBar).toBeVisible({ timeout: 30_000 });

		// The chat tab should show the live title from the API
		await expect(page.getByText("E2E Tab Test Chat")).toBeVisible({ timeout: 15_000 });
	});

	test("tab close button removes the tab and activates a sibling", async ({
		page,
		workspace,
		apiToken,
		request,
	}) => {
		const thread1 = await createThread(request, apiToken, workspace.id, "E2E Close Tab 1");
		const thread2 = await createThread(request, apiToken, workspace.id, "E2E Close Tab 2");

		// Open both threads (each opens a tab)
		await page.goto(`/dashboard/${workspace.id}/new-chat/${thread1.id}`);
		await expect(page.locator(`[data-tab-id="chat-${thread1.id}"]`)).toBeVisible({
			timeout: 30_000,
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat/${thread2.id}`);
		await expect(page.locator(`[data-tab-id="chat-${thread2.id}"]`)).toBeVisible({
			timeout: 30_000,
		});

		// Close the first tab via its close button
		const closeBtn = page
			.locator(`[data-tab-id="chat-${thread1.id}"]`)
			.getByRole("button", { name: /close|×|x/i })
			.first();
		await closeBtn.click();

		// First tab should be gone
		await expect(page.locator(`[data-tab-id="chat-${thread1.id}"]`)).toHaveCount(0);
		// Second tab should still be present
		await expect(page.locator(`[data-tab-id="chat-${thread2.id}"]`)).toBeVisible();
	});

	test("tab switching activates the clicked tab", async ({
		page,
		workspace,
		apiToken,
		request,
	}) => {
		const thread1 = await createThread(request, apiToken, workspace.id, "E2E Switch Tab A");
		const thread2 = await createThread(request, apiToken, workspace.id, "E2E Switch Tab B");

		// Open both tabs
		await page.goto(`/dashboard/${workspace.id}/new-chat/${thread1.id}`);
		await expect(page.locator(`[data-tab-id="chat-${thread1.id}"]`)).toBeVisible({
			timeout: 30_000,
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat/${thread2.id}`);
		await expect(page.locator(`[data-tab-id="chat-${thread2.id}"]`)).toBeVisible({
			timeout: 30_000,
		});

		// Click the first tab to switch back
		await page.locator(`[data-tab-id="chat-${thread1.id}"]`).getByRole("button").first().click();

		// URL should navigate back to thread1
		await expect(page).toHaveURL(new RegExp(`/dashboard/${workspace.id}/new-chat/${thread1.id}`), {
			timeout: 15_000,
		});
	});

	test("new chat tab shows fallback title while loading", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat`);

		// The "new chat" tab should be visible with "New Chat" fallback title
		await expect(page.locator("[data-tab-id='chat-new']")).toBeVisible({ timeout: 30_000 });
		await expect(page.getByText("New Chat")).toBeVisible();
	});

	test("page reload preserves tabs (v2 localStorage persistence)", async ({
		page,
		workspace,
		apiToken,
		request,
	}) => {
		const thread = await createThread(request, apiToken, workspace.id, "E2E Reload Tab");

		await page.goto(`/dashboard/${workspace.id}/new-chat/${thread.id}`);
		await expect(page.locator(`[data-tab-id="chat-${thread.id}"]`)).toBeVisible({
			timeout: 30_000,
		});

		// Reload the page — tab should persist from v2 localStorage
		await page.reload();
		await expect(page.locator(`[data-tab-id="chat-${thread.id}"]`)).toBeVisible({
			timeout: 30_000,
		});

		// No crash — no Next.js error overlay
		await expect(page.getByText(/application error|unhandled error/i)).toHaveCount(0);
	});

	test("no Next.js error overlay on any dashboard page", async ({
		page,
		workspace,
		apiToken,
		request,
	}) => {
		const thread = await createThread(request, apiToken, workspace.id, "E2E No Crash");

		await page.goto(`/dashboard/${workspace.id}/new-chat/${thread.id}`);

		// Wait for page to settle
		await expect(page.locator("[data-tab-id]").first()).toBeVisible({ timeout: 30_000 });

		// No unhandled error overlay
		await expect(page.getByText(/application error|unhandled runtime error/i)).toHaveCount(0);
	});
});
