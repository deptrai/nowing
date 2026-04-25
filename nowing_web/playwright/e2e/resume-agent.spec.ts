import { test, expect } from "../support/merged-fixtures";

/**
 * E2E tests — Background Agent Resume (Story 9-UX-1b)
 *
 * These tests mock the /runs/* endpoints so they run without a live backend.
 * They assert that:
 *   P0: Active running run → orchestra strip replays persisted events on mount
 *   P1: Abandoned run → resume banner appears, clicking Resume re-attaches stream
 */

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildSSEStream(events: Array<{ type?: string; data?: object; raw?: string }>): string {
	return (
		events
			.map((e) => {
				if (e.raw) return e.raw;
				return `event: ${e.type}\ndata: ${JSON.stringify(e.data)}\n\n`;
			})
			.join("") + 'event: run-replay-end\ndata: {"seq":5,"status":"completed"}\n\n'
	);
}

function replaySSE(): string {
	return buildSSEStream([
		{
			type: "orchestra-spawn",
			data: {
				sessionId: "42-run-abc",
				agentId: "agent-tokenomics",
				agentName: "Tokenomics",
				agentType: "tokenomics",
			},
		},
		{
			type: "orchestra-update",
			data: {
				sessionId: "42-run-abc",
				agentId: "agent-tokenomics",
				status: "running",
			},
		},
		{
			type: "orchestra-done",
			data: {
				sessionId: "42-run-abc",
				agentId: "agent-tokenomics",
			},
		},
		{
			type: "orchestra-complete",
			data: {
				sessionId: "42-run-abc",
				agentIds: ["agent-tokenomics"],
				citationCount: 3,
			},
		},
	]);
}

const MOCK_RUNNING_RUN = {
	id: "run-abc-0001",
	thread_id: 42,
	session_id: "42-run-abc",
	status: "running",
	user_query: "Analyse BTC tokenomics",
	started_at: new Date().toISOString(),
	completed_at: null,
	final_message_id: null,
};

const MOCK_ABANDONED_RUN = {
	...MOCK_RUNNING_RUN,
	id: "run-abc-0002",
	status: "abandoned",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Resume: running run replays on mount", () => {
	test("orchestra events replay when a running run is found on page load", async ({
		page,
		intercept,
	}) => {
		// Mock active runs endpoint to return a running run
		await intercept.mockRoute({
			url: "**/api/v1/threads/*/runs/active",
			response: {
				status: 200,
				body: JSON.stringify([MOCK_RUNNING_RUN]),
				headers: { "Content-Type": "application/json" },
			},
		});

		// Mock stream endpoint to return pre-recorded SSE events
		await intercept.mockRoute({
			url: `**/api/v1/threads/*/runs/${MOCK_RUNNING_RUN.id}/stream**`,
			response: {
				status: 200,
				body: replaySSE(),
				headers: {
					"Content-Type": "text/event-stream",
					"Cache-Control": "no-cache",
				},
			},
		});

		// Navigate to a chat thread (thread 42)
		await page.goto("/dashboard/1/new-chat/42");

		// The orchestra strip should appear after replaying events
		await expect(page.locator("[data-testid='orchestra-strip']")).toBeVisible({
			timeout: 10_000,
		});
	});
});

test.describe("Resume: abandoned run shows Resume banner", () => {
	test("abandoned run shows Resume button and hides banner after resuming", async ({
		page,
		intercept,
	}) => {
		// Mock active runs endpoint to return an abandoned run
		await intercept.mockRoute({
			url: "**/api/v1/threads/*/runs/active",
			response: {
				status: 200,
				body: JSON.stringify([MOCK_ABANDONED_RUN]),
				headers: { "Content-Type": "application/json" },
			},
		});

		// Mock resume endpoint
		await intercept.mockRoute({
			url: `**/api/v1/threads/*/runs/${MOCK_ABANDONED_RUN.id}/resume`,
			response: {
				status: 200,
				body: JSON.stringify({ ...MOCK_ABANDONED_RUN, status: "running" }),
				headers: { "Content-Type": "application/json" },
			},
		});

		// Mock stream for resumed run
		await intercept.mockRoute({
			url: `**/api/v1/threads/*/runs/${MOCK_ABANDONED_RUN.id}/stream**`,
			response: {
				status: 200,
				body: replaySSE(),
				headers: { "Content-Type": "text/event-stream" },
			},
		});

		await page.goto("/dashboard/1/new-chat/42");

		// Resume banner should appear
		const resumeBtn = page.getByRole("button", { name: "Resume" });
		await expect(resumeBtn).toBeVisible({ timeout: 10_000 });

		// Click Resume
		await resumeBtn.click();

		// Banner should disappear after resuming
		await expect(resumeBtn).not.toBeVisible({ timeout: 5_000 });
	});
});
