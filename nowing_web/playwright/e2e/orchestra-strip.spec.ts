import { test, expect } from "../support/merged-fixtures";

/**
 * E2E tests — Orchestra Conductor Strip (Story 9-FE-1)
 *
 * These tests mock the SSE endpoint so they run without a live backend.
 * They assert on the DOM rendered by `OrchestraStrip` and `DegradationNotice`.
 *
 * Covers:
 *   P0: Happy-path — 4 agents spawn, transition to running, complete → strip collapses
 *   P0: Degradation — inject orchestra-fail → amber DegradationNotice appears
 *   P1: All-fail → outcome "failed", strip remains with notice
 *   P1: Single-agent happy-path → no strip wrapper, inline status only
 */

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a newline-delimited SSE stream string from an array of events */
function buildSSEStream(events: Array<{ type: string; data: object }>): string {
	return (
		events.map((e) => `data: ${JSON.stringify({ type: e.type, data: e.data })}\n`).join("\n") + "\n"
	);
}

const SESSION_ID = "e2e-sess-001";

const FOUR_AGENTS = [
	{ agentId: "a1", agentName: "CoinGecko", agentType: "price" },
	{ agentId: "a2", agentName: "Binance", agentType: "exchange" },
	{ agentId: "a3", agentName: "Chainlink", agentType: "oracle" },
	{ agentId: "a4", agentName: "DeFiLlama", agentType: "tvl" },
];

/** Full happy-path SSE sequence: spawn → running → done → complete */
function happyPathSSE(): string {
	const events: Array<{ type: string; data: object }> = [];

	// Spawn all 4
	for (const agent of FOUR_AGENTS) {
		events.push({
			type: "orchestra-spawn",
			data: { sessionId: SESSION_ID, ...agent },
		});
	}

	// Update all to running
	for (const agent of FOUR_AGENTS) {
		events.push({
			type: "orchestra-update",
			data: { sessionId: SESSION_ID, agentId: agent.agentId, status: "running" },
		});
	}

	// Done all 4
	for (const agent of FOUR_AGENTS) {
		events.push({
			type: "orchestra-done",
			data: {
				sessionId: SESSION_ID,
				agentId: agent.agentId,
				citationIds: [`cit-${agent.agentId}-1`],
			},
		});
	}

	// Complete
	events.push({
		type: "orchestra-complete",
		data: {
			sessionId: SESSION_ID,
			agentIds: FOUR_AGENTS.map((a) => a.agentId),
			citationCount: 4,
		},
	});

	// End-of-stream sentinel
	events.push({ type: "done", data: {} });

	return buildSSEStream(events);
}

/** Degradation SSE: 3 done, 1 failed */
function degradationSSE(): string {
	const events: Array<{ type: string; data: object }> = [];

	for (const agent of FOUR_AGENTS) {
		events.push({
			type: "orchestra-spawn",
			data: { sessionId: SESSION_ID, ...agent },
		});
	}

	for (const agent of FOUR_AGENTS) {
		events.push({
			type: "orchestra-update",
			data: { sessionId: SESSION_ID, agentId: agent.agentId, status: "running" },
		});
	}

	// 3 done
	for (const agent of FOUR_AGENTS.slice(0, 3)) {
		events.push({
			type: "orchestra-done",
			data: { sessionId: SESSION_ID, agentId: agent.agentId, citationIds: [] },
		});
	}

	// 1 failed
	events.push({
		type: "orchestra-fail",
		data: {
			sessionId: SESSION_ID,
			agentId: "a4",
			errorCode: "timeout",
			errorMessage: "DeFiLlama timed out",
		},
	});

	// Complete
	events.push({
		type: "orchestra-complete",
		data: {
			sessionId: SESSION_ID,
			agentIds: FOUR_AGENTS.map((a) => a.agentId),
			citationCount: 3,
		},
	});

	events.push({ type: "done", data: {} });

	return buildSSEStream(events);
}

/** All-fail SSE: all 4 agents fail */
function allFailSSE(): string {
	const events: Array<{ type: string; data: object }> = [];

	for (const agent of FOUR_AGENTS) {
		events.push({
			type: "orchestra-spawn",
			data: { sessionId: SESSION_ID, ...agent },
		});
	}

	for (const agent of FOUR_AGENTS) {
		events.push({
			type: "orchestra-fail",
			data: {
				sessionId: SESSION_ID,
				agentId: agent.agentId,
				errorCode: "unavailable",
				errorMessage: "Service down",
			},
		});
	}

	events.push({
		type: "orchestra-complete",
		data: { sessionId: SESSION_ID, agentIds: FOUR_AGENTS.map((a) => a.agentId), citationCount: 0 },
	});

	events.push({ type: "done", data: {} });

	return buildSSEStream(events);
}

/** Single-agent happy-path SSE */
function singleAgentSSE(): string {
	const events: Array<{ type: string; data: object }> = [
		{
			type: "orchestra-spawn",
			data: { sessionId: SESSION_ID, agentId: "a1", agentName: "CoinGecko", agentType: "price" },
		},
		{
			type: "orchestra-update",
			data: { sessionId: SESSION_ID, agentId: "a1", status: "running" },
		},
		{
			type: "orchestra-done",
			data: { sessionId: SESSION_ID, agentId: "a1", citationIds: ["cit-1"] },
		},
		{
			type: "orchestra-complete",
			data: { sessionId: SESSION_ID, agentIds: ["a1"], citationCount: 1 },
		},
		{ type: "done", data: {} },
	];
	return buildSSEStream(events);
}

// ---------------------------------------------------------------------------
// Route helper — intercepts the chat send endpoint and streams SSE
// ---------------------------------------------------------------------------

async function mockChatSSE(page: import("@playwright/test").Page, sseBody: string) {
	// P6: backend SSE endpoint is /api/v1/chat (Epic 7). The previous glob
	// "**/api/chat/**" never matched because "/api/v1/chat" has "v1" between
	// "/api/" and "/chat". Match both v1 path and any future unversioned form.
	await page.route(/\/api\/(v\d+\/)?chat(\/.*)?$/, async (route) => {
		const headers = {
			"Content-Type": "text/event-stream",
			"Cache-Control": "no-cache",
			Connection: "keep-alive",
		};
		await route.fulfill({ status: 200, headers, body: sseBody });
	});
	// Also intercept the thread creation / resume endpoints
	await page.route(/\/api\/(v\d+\/)?threads(\/.*)?$/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({ id: "thread-e2e-001", sessionId: SESSION_ID }),
		});
	});
}

// ---------------------------------------------------------------------------
// Fixture helper — navigate to a chat page
// Note: Uses spaceId "demo" which should be present in test env, or the test
// will skip gracefully if the route requires auth. The orchestra strip logic
// is purely client-side (atom-driven) so these tests focus on that layer.
// ---------------------------------------------------------------------------

const BASE_CHAT_URL = "/dashboard/demo/new-chat";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Orchestra Conductor Strip", () => {
	// -------------------------------------------------------------------------
	// P0 — Happy-path: 4 agents full lifecycle
	// -------------------------------------------------------------------------

	test("happy-path: 4 agents spawn, run, complete → strip collapses to summary", async ({
		page,
		log,
	}) => {
		await mockChatSSE(page, happyPathSSE());

		await log({ level: "step", message: "Navigate to chat page" });
		await page.goto(BASE_CHAT_URL);

		// Submit a query to trigger the SSE stream
		await log({ level: "step", message: "Submit a query" });
		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		await input.fill("What is the BTC price?");
		await page.keyboard.press("Enter");

		// After spawn: strip should be visible with 4 agent rows
		await log({ level: "step", message: "Verify orchestra strip appears" });
		const strip = page.locator('[data-slot="orchestra-strip"]');
		await expect(strip).toBeVisible({ timeout: 15_000 });

		// Initially in default variant with agent rows
		await expect(strip).toHaveAttribute("data-variant", "research-lab");

		// All 4 agent names visible
		for (const agent of FOUR_AGENTS) {
			await expect(page.getByText(agent.agentName).first()).toBeVisible();
		}

		// After complete: strip collapses
		await log({ level: "step", message: "Verify strip collapses after completion" });
		await expect(strip).toHaveAttribute("data-variant", "collapsed", { timeout: 20_000 });

		// Summary line: "4/4 done"
		await expect(page.getByText(/4\/4 done/)).toBeVisible();

		// No degradation notice
		const degradationAlert = page.locator('[role="alert"]');
		await expect(degradationAlert).not.toBeVisible();
	});

	// -------------------------------------------------------------------------
	// P0 — Degradation: 1 agent fails → amber DegradationNotice appears
	// -------------------------------------------------------------------------

	test("degradation: 1 agent fails → amber notice shows '3/4 sources completed'", async ({
		page,
		log,
	}) => {
		await mockChatSSE(page, degradationSSE());

		await log({ level: "step", message: "Navigate to chat page" });
		await page.goto(BASE_CHAT_URL);

		await log({ level: "step", message: "Submit query" });
		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		await input.fill("ETH price breakdown");
		await page.keyboard.press("Enter");

		// Wait for strip
		const strip = page.locator('[data-slot="orchestra-strip"]');
		await expect(strip).toBeVisible({ timeout: 15_000 });

		// Wait for completion (partial outcome)
		await expect(strip).toHaveAttribute("data-variant", "collapsed", { timeout: 20_000 });

		// DegradationNotice should appear with amber styling
		await log({ level: "step", message: "Verify degradation notice appears" });
		const notice = page.locator('[role="alert"]');
		await expect(notice).toBeVisible();

		// Summary text: "3/4 sources completed · 1 degraded"
		await expect(notice.getByText(/3\/4 sources completed/)).toBeVisible();
		await expect(notice.getByText(/1 degraded/)).toBeVisible();

		// Expand to see failed agent detail
		await log({ level: "step", message: "Expand degradation notice" });
		const expandBtn = notice.getByRole("button", { name: /expand degradation/i });
		await expandBtn.click();

		// DeFiLlama should appear as the failed agent
		await expect(notice.getByText("DeFiLlama")).toBeVisible();
		await expect(notice.getByText(/Timed out/)).toBeVisible();
	});

	// -------------------------------------------------------------------------
	// P1 — All agents fail → outcome "failed", strip stays with full notice
	// -------------------------------------------------------------------------

	test("all-fail: all 4 agents fail → strip not collapsed, degradation shows all failures", async ({
		page,
		log,
	}) => {
		await mockChatSSE(page, allFailSSE());

		await page.goto(BASE_CHAT_URL);

		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		await input.fill("Solana price");
		await page.keyboard.press("Enter");

		const strip = page.locator('[data-slot="orchestra-strip"]');
		await expect(strip).toBeVisible({ timeout: 15_000 });

		// outcome "failed" — strip should NOT show "collapsed" variant
		// (DegradationNotice renders, but no success summary line)
		await expect(strip).not.toHaveAttribute("data-variant", "collapsed", { timeout: 20_000 });

		// All 4 agents failed — degradation notice present
		const notice = page.locator('[role="alert"]');
		await expect(notice).toBeVisible();

		// 0/4 sources completed
		await expect(notice.getByText(/0\/4 sources completed/)).toBeVisible();
		await expect(notice.getByText(/4 degraded/)).toBeVisible();
	});

	// -------------------------------------------------------------------------
	// P1 — Single agent: no strip wrapper, inline status only
	// -------------------------------------------------------------------------

	test("single-agent: renders inline status without strip wrapper", async ({ page, log }) => {
		await mockChatSSE(page, singleAgentSSE());

		await page.goto(BASE_CHAT_URL);

		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		await input.fill("BTC quick check");
		await page.keyboard.press("Enter");

		// Single-agent variant
		const strip = page.locator('[data-slot="orchestra-strip"][data-variant="single-agent"]');
		await expect(strip).toBeVisible({ timeout: 15_000 });

		// Agent name inline
		await expect(strip.getByText("CoinGecko")).toBeVisible();

		// No bordered card wrapper (no "rounded-lg border" class at strip level)
		await expect(
			page.locator('[data-slot="orchestra-strip"][data-variant="research-lab"]')
		).not.toBeVisible();
	});
});
