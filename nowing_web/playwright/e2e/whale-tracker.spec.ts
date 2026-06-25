import { test, expect } from "../support/merged-fixtures";

/**
 * E2E tests — Whale Tracker sub-agent & dynamic grid layout (Story 9-UX-4 T14/T15)
 *
 * Covers:
 *   T14 (AC10): Feature flag ON → 7 agents spawn including whale_tracker; whale section visible
 *   T15 (AC11): Dynamic grid at md breakpoint renders 7 lanes without overflow;
 *               flag OFF regression → 6 lanes, no whale_tracker lane
 *
 * Both suites mock the SSE endpoint so no real backend is required.
 */

// ─── Helpers ─────────────────────────────────────────────────────────────────

type SSEEventInput =
	| { type: string; data?: object; delta?: never }
	| { delta: string; type?: never; data?: never };

function buildSSEStream(events: Array<SSEEventInput>): string {
	return events
		.map((e) => {
			if (e.delta !== undefined) {
				return `data: ${JSON.stringify({ type: "text-delta", delta: e.delta })}\n\n`;
			}
			return `data: ${JSON.stringify({ type: e.type, data: e.data })}\n\n`;
		})
		.join("");
}

const SESSION_ID = "e2e-whale-001";

/** The 6 base agents that are always present */
const BASE_AGENTS = [
	{ agentId: "tokenomics_analyst", agentName: "Tokenomics Analyst", agentType: "tokenomics" },
	{ agentId: "defillama_analyst", agentName: "DeFi Analyst", agentType: "defillama" },
	{ agentId: "yield_optimizer", agentName: "Yield Optimizer", agentType: "yield" },
	{ agentId: "smart_contract_analyst", agentName: "Security Analyst", agentType: "smart_contract" },
	{ agentId: "news_analyst", agentName: "News Analyst", agentType: "news" },
	{ agentId: "sentiment_analyst", agentName: "Sentiment Analyst", agentType: "sentiment" },
];

const WHALE_AGENT = {
	agentId: "whale_tracker",
	agentName: "Whale Tracker",
	agentType: "whale_tracker",
};

function makeOrchestrationSSE(agents: typeof BASE_AGENTS): string {
	const events: Array<{ type: string; data?: object }> = [];

	// Spawn all agents
	for (const a of agents) {
		events.push({ type: "orchestra-spawn", data: { sessionId: SESSION_ID, ...a } });
	}
	// Mark all running
	for (const a of agents) {
		events.push({
			type: "orchestra-update",
			data: { sessionId: SESSION_ID, agentId: a.agentId, status: "running" },
		});
	}
	// Whale tracker narration (only if present)
	if (agents.some((a) => a.agentId === "whale_tracker")) {
		events.push({
			type: "data-orchestra-narration",
			data: {
				sessionId: SESSION_ID,
				agentId: "whale_tracker",
				text: "Đang tra cứu Nansen smart-money flows...",
				tone: "fetching",
			},
		});
		events.push({
			type: "data-orchestra-source-fetched",
			data: {
				sessionId: SESSION_ID,
				agentId: "whale_tracker",
				source: {
					domain: "nansen.ai",
					favicon: "https://icons.duckduckgo.com/ip3/nansen.ai.ico",
					url: "",
					dataType: "on_chain",
				},
			},
		});
	}
	// Done + complete
	for (const a of agents) {
		events.push({
			type: "orchestra-done",
			data: { sessionId: SESSION_ID, agentId: a.agentId, citationIds: [] },
		});
	}
	events.push({
		type: "orchestra-complete",
		data: { sessionId: SESSION_ID, agentIds: agents.map((a) => a.agentId), citationCount: 0 },
	});

	return buildSSEStream([
		...events.map((e) => e as SSEEventInput),
		{ delta: "Phân tích toàn diện hoàn thành." },
	]);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function mockChatSSE(page: any, sseBody: string) {
	await page.route(/\/api\/(v\d+\/)?chat(\/.*)?$/, async (route: import("@playwright/test").Route) => {
		await route.fulfill({
			status: 200,
			headers: {
				"Content-Type": "text/event-stream",
				"Cache-Control": "no-cache",
				Connection: "keep-alive",
			},
			body: sseBody,
		});
	});
	await page.route(/\/api\/(v\d+\/)?threads(\/.*)?$/, async (route: import("@playwright/test").Route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({ id: "thread-e2e-whale", sessionId: SESSION_ID }),
		});
	});
}

const BASE_CHAT_URL = "/dashboard/demo/new-chat";

async function submitQuery(page: any, query: string) {
	const input = page
		.getByTestId("chat-input")
		.or(page.getByRole("textbox", { name: /message|query|ask/i }));
	await input.fill(query);
	await page.keyboard.press("Enter");
}

// ─── T14: Feature flag ON — whale_tracker spawns + whale section visible ──────

test.describe("Whale Tracker — flag ON (9-UX-4 T14)", () => {
	test("AC10: 7 agents spawn when whale_tracker enabled", async ({ page, log }) => {
		const sseBody = makeOrchestrationSSE([...BASE_AGENTS, WHALE_AGENT]);
		await mockChatSSE(page, sseBody);
		await page.goto(BASE_CHAT_URL);
		await submitQuery(page, "phân tích toàn diện ETH");

		const grid = page.locator('[data-slot="agent-grid"]');
		await expect(grid).toBeVisible({ timeout: 15_000 });

		// All 7 agent lanes present
		const lanes = grid.locator('[data-slot="agent-lane"]');
		await expect(lanes).toHaveCount(7, { timeout: 15_000 });
	});

	test("AC10: whale_tracker lane visible with Whale Tracker label", async ({ page, log }) => {
		const sseBody = makeOrchestrationSSE([...BASE_AGENTS, WHALE_AGENT]);
		await mockChatSSE(page, sseBody);
		await page.goto(BASE_CHAT_URL);
		await submitQuery(page, "phân tích toàn diện ETH");

		await expect(page.getByText("Whale Tracker").first()).toBeVisible({ timeout: 15_000 });
	});

	test("AC10: whale_tracker narration shows Nansen source chip", async ({ page, log }) => {
		const sseBody = makeOrchestrationSSE([...BASE_AGENTS, WHALE_AGENT]);
		await mockChatSSE(page, sseBody);
		await page.goto(BASE_CHAT_URL);
		await submitQuery(page, "phân tích toàn diện ETH");

		await expect(page.getByText("Đang tra cứu Nansen smart-money flows...")).toBeVisible({
			timeout: 15_000,
		});
		await expect(page.getByText("nansen.ai")).toBeVisible({ timeout: 15_000 });
	});
});

// ─── T15: Dynamic grid layout — 7 vs 6 lanes, no overflow ────────────────────

test.describe("Dynamic grid layout — 7 vs 6 lanes (9-UX-4 T15)", () => {
	test("AC11: 7-agent grid has no horizontal overflow at md breakpoint (768px)", async ({
		page,
		log,
	}) => {
		const sseBody = makeOrchestrationSSE([...BASE_AGENTS, WHALE_AGENT]);
		await mockChatSSE(page, sseBody);
		await page.setViewportSize({ width: 768, height: 900 });
		await page.goto(BASE_CHAT_URL);
		await submitQuery(page, "phân tích toàn diện ETH");

		const grid = page.locator('[data-slot="agent-grid"]');
		await expect(grid).toBeVisible({ timeout: 15_000 });

		// scrollWidth should not exceed clientWidth — no overflow
		const hasOverflow = await grid.evaluate((el: Element) => el.scrollWidth > el.clientWidth);
		expect(hasOverflow).toBe(false);
	});

	test("AC11: 6-agent grid (flag OFF) has 6 lanes, no whale_tracker lane", async ({
		page,
		log,
	}) => {
		const sseBody = makeOrchestrationSSE(BASE_AGENTS); // 6 agents, no whale_tracker
		await mockChatSSE(page, sseBody);
		await page.goto(BASE_CHAT_URL);
		await submitQuery(page, "phân tích toàn diện ETH");

		const grid = page.locator('[data-slot="agent-grid"]');
		await expect(grid).toBeVisible({ timeout: 15_000 });

		const lanes = grid.locator('[data-slot="agent-lane"]');
		await expect(lanes).toHaveCount(6, { timeout: 15_000 });

		// Whale Tracker lane must NOT appear
		await expect(page.getByText("Whale Tracker")).not.toBeVisible();
	});

	test("AC11: 6-agent grid has no horizontal overflow at md breakpoint", async ({ page, log }) => {
		const sseBody = makeOrchestrationSSE(BASE_AGENTS);
		await mockChatSSE(page, sseBody);
		await page.setViewportSize({ width: 768, height: 900 });
		await page.goto(BASE_CHAT_URL);
		await submitQuery(page, "phân tích toàn diện ETH");

		const grid = page.locator('[data-slot="agent-grid"]');
		await expect(grid).toBeVisible({ timeout: 15_000 });

		const hasOverflow = await grid.evaluate((el: Element) => el.scrollWidth > el.clientWidth);
		expect(hasOverflow).toBe(false);
	});

	test("AC11: 7-agent grid has no horizontal overflow at desktop (1280px)", async ({
		page,
		log,
	}) => {
		const sseBody = makeOrchestrationSSE([...BASE_AGENTS, WHALE_AGENT]);
		await mockChatSSE(page, sseBody);
		await page.setViewportSize({ width: 1280, height: 900 });
		await page.goto(BASE_CHAT_URL);
		await submitQuery(page, "phân tích toàn diện ETH");

		const grid = page.locator('[data-slot="agent-grid"]');
		await expect(grid).toBeVisible({ timeout: 15_000 });

		const hasOverflow = await grid.evaluate((el: Element) => el.scrollWidth > el.clientWidth);
		expect(hasOverflow).toBe(false);
	});
});
