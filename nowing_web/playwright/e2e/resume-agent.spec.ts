import { test, expect } from "../support/merged-fixtures";

/**
 * E2E tests — Background Agent Resume (Story 9-UX-1b/1c)
 *
 * These tests mock the /runs/* endpoints so they run without a live backend.
 * They assert that:
 *   P0: Active running run → orchestra strip replays persisted events on mount
 *   P1: Abandoned run → Resume button in strip header, clicking Resume re-attaches stream
 *
 * Wire format: bare `data: {json}\n\n` (Vercel UI Stream, T1).
 * Sentinels: `{"_marker":"replay-end","status":"..."}` (T22).
 */

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Emit a single Vercel UI Stream event line. */
function sseEvent(payload: object): string {
	return `data: ${JSON.stringify(payload)}\n\n`;
}

function replaySSE(status: "completed" | "live" | "abandoned" = "completed"): string {
	const events = [
		sseEvent({ _marker: "replay-start" }),
		sseEvent({
			type: "orchestra-spawn",
			data: {
				sessionId: "run-abc-0001",
				agentId: "agent-tokenomics",
				agentName: "Tokenomics",
				agentType: "tokenomics",
			},
		}),
		sseEvent({
			type: "orchestra-update",
			data: { sessionId: "run-abc-0001", agentId: "agent-tokenomics", status: "running" },
		}),
		sseEvent({
			type: "orchestra-done",
			data: { sessionId: "run-abc-0001", agentId: "agent-tokenomics" },
		}),
		sseEvent({
			type: "orchestra-complete",
			data: { sessionId: "run-abc-0001", agentIds: ["agent-tokenomics"], citationCount: 1 },
		}),
		sseEvent({ _marker: "replay-end", status }),
	];
	return events.join("");
}

const MOCK_RUNNING_RUN = {
	id: "run-abc-0001",
	thread_id: 42,
	session_id: "42-abcd1234",
	langgraph_thread_id: "run-abc-0001",
	status: "running",
	user_query: "Analyse BTC tokenomics",
	started_at: new Date().toISOString(),
	completed_at: null,
	final_message_id: null,
};

const MOCK_ABANDONED_RUN = {
	...MOCK_RUNNING_RUN,
	id: "run-abc-0002",
	langgraph_thread_id: "run-abc-0002",
	status: "abandoned",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Resume: running run replays on mount", () => {
	test("orchestra events replay when a running run is found on page load", async ({
		page,
		intercept,
		// biome-ignore lint/suspicious/noExplicitAny: Playwright fixture types depend on merged-fixtures
	}: any) => {
		await intercept.mockRoute({
			url: "**/api/v1/threads/*/runs/active",
			response: {
				status: 200,
				body: JSON.stringify([MOCK_RUNNING_RUN]),
				headers: { "Content-Type": "application/json" },
			},
		});

		await intercept.mockRoute({
			url: `**/api/v1/threads/*/runs/${MOCK_RUNNING_RUN.id}/stream**`,
			response: {
				status: 200,
				body: replaySSE("completed"),
				headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
			},
		});

		await page.goto("/dashboard/1/new-chat/42");

		// Orchestra strip should appear after replay
		await expect(page.locator("[data-slot='orchestra-strip']")).toBeVisible({ timeout: 10_000 });
	});
});

test.describe("Resume: abandoned run shows Resume button in strip", () => {
	test("abandoned run shows Resume button in strip header and clears after click", async ({
		page,
		intercept,
		// biome-ignore lint/suspicious/noExplicitAny: Playwright fixture types depend on merged-fixtures
	}: any) => {
		await intercept.mockRoute({
			url: "**/api/v1/threads/*/runs/active",
			response: {
				status: 200,
				body: JSON.stringify([MOCK_ABANDONED_RUN]),
				headers: { "Content-Type": "application/json" },
			},
		});

		// Replay SSE for the abandoned run (returns replay-end with status=abandoned)
		await intercept.mockRoute({
			url: `**/api/v1/threads/*/runs/${MOCK_ABANDONED_RUN.id}/stream**`,
			response: {
				status: 200,
				body: replaySSE("abandoned"),
				headers: { "Content-Type": "text/event-stream" },
			},
		});

		// Resume endpoint returns a new running run
		const RESUMED_RUN = { ...MOCK_ABANDONED_RUN, status: "running" };
		await intercept.mockRoute({
			url: `**/api/v1/threads/*/runs/${MOCK_ABANDONED_RUN.id}/resume`,
			response: {
				status: 200,
				body: JSON.stringify(RESUMED_RUN),
				headers: { "Content-Type": "application/json" },
			},
		});

		// Mock stream for resumed run (bare data lines, T1 format)
		await intercept.mockRoute({
			url: `**/api/v1/threads/*/runs/${MOCK_ABANDONED_RUN.id}/stream**`,
			response: {
				status: 200,
				body: replaySSE("live") + sseEvent({ _marker: "run-end" }),
				headers: { "Content-Type": "text/event-stream" },
			},
		});

		await page.goto("/dashboard/1/new-chat/42");

		// T21: Resume button should appear in strip header (not a separate banner)
		const resumeBtn = page.getByRole("button", { name: "Resume" });
		await expect(resumeBtn).toBeVisible({ timeout: 10_000 });

		// Click Resume — button should disappear after resuming
		await resumeBtn.click();
		await expect(resumeBtn).not.toBeVisible({ timeout: 5_000 });
	});
});

test.describe("Resume: strip uses bare data: format (T1 wire contract)", () => {
	test("strip renders correctly with bare data: lines (no event: header)", async ({
		page,
		intercept,
		// biome-ignore lint/suspicious/noExplicitAny: Playwright fixture types depend on merged-fixtures
	}: any) => {
		await intercept.mockRoute({
			url: "**/api/v1/threads/*/runs/active",
			response: {
				status: 200,
				body: JSON.stringify([MOCK_RUNNING_RUN]),
				headers: { "Content-Type": "application/json" },
			},
		});

		// Bare data: format only — no event: headers
		const bareStream = [
			sseEvent({ _marker: "replay-start" }),
			sseEvent({
				type: "orchestra-spawn",
				data: {
					sessionId: "run-abc-0001",
					agentId: "a1",
					agentName: "DeFiLlama",
					agentType: "tvl",
				},
			}),
			sseEvent({
				type: "orchestra-spawn",
				data: {
					sessionId: "run-abc-0001",
					agentId: "a2",
					agentName: "CoinGecko",
					agentType: "price",
				},
			}),
			sseEvent({ _marker: "replay-end", status: "live" }),
		].join("");

		await intercept.mockRoute({
			url: `**/api/v1/threads/*/runs/${MOCK_RUNNING_RUN.id}/stream**`,
			response: {
				status: 200,
				body: bareStream,
				headers: { "Content-Type": "text/event-stream" },
			},
		});

		await page.goto("/dashboard/1/new-chat/42");

		// Multi-agent strip: should show agent grid
		await expect(page.locator("[data-slot='agent-grid']")).toBeVisible({ timeout: 10_000 });
		await expect(page.locator("[data-slot='orchestra-strip']").first()).toBeVisible();
	});
});
