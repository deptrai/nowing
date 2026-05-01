import { test, expect } from "../support/merged-fixtures";

/**
 * E2E tests — Live Research Lab (Story 9-UX-1)
 *
 * Mocks the SSE endpoint to emit the Phase 2 UX events:
 *   data-orchestra-narration, data-orchestra-source-fetched,
 *   data-orchestra-fact-captured, data-orchestra-model-attribution,
 *   data-orchestra-rate-gate-wait
 *
 * Covers:
 *   AC2: Pre-call narration appears in agent lane while running
 *   AC3: Source favicon chips appear after source-fetched event
 *   AC4: Fact counter increments per fact-captured event
 *   AC9: Model attribution badge renders in agent lane
 *   AC12: Rate-gate banner appears when rate-gate-wait event fires
 *   AC6: Agent grid uses research-lab variant (not "default")
 */

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type SSEEventInput =
	| { type: string; data?: object; delta?: never }
	| { delta: string; type?: never; data?: never };

function buildSSEStream(events: Array<SSEEventInput>): string {
	// SSE spec: each event is a single `data:` line followed by a blank-line
	// terminator (\n\n). Joining with `\n` between events would merge them into
	// a single multi-line event for some parsers.
	return events
		.map((e) => {
			if (e.delta !== undefined) {
				return `data: ${JSON.stringify({ type: "text-delta", delta: e.delta })}\n\n`;
			}
			return `data: ${JSON.stringify({ type: e.type, data: e.data })}\n\n`;
		})
		.join("");
}

const SESSION_ID = "e2e-lab-001";
const AGENT_ID = "tokenomics_analyst";
const AGENT_NAME = "Tokenomics Analyst";

/** SSE stream exercising all 5 Phase 2 UX event types */
function labSSE(): string {
	return buildSSEStream([
		// Spawn one agent
		{
			type: "orchestra-spawn",
			data: {
				sessionId: SESSION_ID,
				agentId: AGENT_ID,
				agentName: AGENT_NAME,
				agentType: "tokenomics",
			},
		},
		// Running
		{
			type: "orchestra-update",
			data: { sessionId: SESSION_ID, agentId: AGENT_ID, status: "running" },
		},
		// Model attribution
		{
			type: "data-orchestra-model-attribution",
			data: {
				sessionId: SESSION_ID,
				agentId: AGENT_ID,
				model: "claude-sonnet-4-6",
				provider: "trollllm",
			},
		},
		// Pre-call narration
		{
			type: "data-orchestra-narration",
			data: {
				sessionId: SESSION_ID,
				agentId: AGENT_ID,
				text: "Đang query CoinGecko cho thông tin token...",
				tone: "fetching",
			},
		},
		// Source fetched
		{
			type: "data-orchestra-source-fetched",
			data: {
				sessionId: SESSION_ID,
				agentId: AGENT_ID,
				source: {
					domain: "coingecko.com",
					favicon: "https://icons.duckduckgo.com/ip3/coingecko.com.ico",
					url: "",
					dataType: "price",
				},
			},
		},
		// Fact captured
		{
			type: "data-orchestra-fact-captured",
			data: { sessionId: SESSION_ID, agentId: AGENT_ID, factSummary: "Price $7.23" },
		},
		// Rate-gate wait
		{
			type: "data-orchestra-rate-gate-wait",
			data: { sessionId: SESSION_ID, waitSeconds: 7.2, reason: "min_interval" },
		},
		// Agent done
		{
			type: "orchestra-done",
			data: { sessionId: SESSION_ID, agentId: AGENT_ID, citationIds: [] },
		},
		// Complete
		{
			type: "orchestra-complete",
			data: { sessionId: SESSION_ID, agentIds: [AGENT_ID], citationCount: 0 },
		},
		// Synthesized text
		{ delta: "Phân tích UNI token hoàn thành." },
	]);
}

/** SSE with multiple agents to exercise grid layout */
function multiAgentLabSSE(): string {
	const agents = [
		{ agentId: "a1", agentName: "Tokenomics Analyst", agentType: "tokenomics" },
		{ agentId: "a2", agentName: "DeFi Analyst", agentType: "defillama" },
		{ agentId: "a3", agentName: "Security Analyst", agentType: "smart_contract" },
		{ agentId: "a4", agentName: "News Analyst", agentType: "news" },
	];

	const events: Array<{ type: string; data?: object }> = [];

	for (const a of agents) {
		events.push({ type: "orchestra-spawn", data: { sessionId: SESSION_ID, ...a } });
	}
	for (const a of agents) {
		events.push({
			type: "orchestra-update",
			data: { sessionId: SESSION_ID, agentId: a.agentId, status: "running" },
		});
	}
	// Add narration for first agent
	events.push({
		type: "data-orchestra-narration",
		data: {
			sessionId: SESSION_ID,
			agentId: "a1",
			text: "Đang phân tích tokenomics...",
			tone: "fetching",
		},
	});
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

	return buildSSEStream(events);
}

// ---------------------------------------------------------------------------
// Route mock helper
// ---------------------------------------------------------------------------

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
			body: JSON.stringify({ id: "thread-e2e-lab", sessionId: SESSION_ID }),
		});
	});
}

const BASE_CHAT_URL = "/dashboard/demo/new-chat";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Live Research Lab (9-UX-1)", () => {
	test("AC6: strip uses research-lab variant (not default)", async ({ page, log }) => {
		await mockChatSSE(page, labSSE());
		await page.goto(BASE_CHAT_URL);

		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		await input.fill("phân tích toàn diện UNI");
		await page.keyboard.press("Enter");

		const strip = page.locator('[data-slot="orchestra-strip"]');
		await expect(strip).toBeVisible({ timeout: 15_000 });
		await expect(strip).toHaveAttribute("data-variant", "research-lab");
	});

	test("AC2: narration text appears in running agent lane", async ({ page, log }) => {
		await mockChatSSE(page, labSSE());
		await page.goto(BASE_CHAT_URL);

		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		await input.fill("phân tích toàn diện UNI");
		await page.keyboard.press("Enter");

		await expect(page.getByText("Đang query CoinGecko cho thông tin token...")).toBeVisible({
			timeout: 15_000,
		});
	});

	test("AC3: source favicon chip appears after source-fetched event", async ({ page, log }) => {
		await mockChatSSE(page, labSSE());
		await page.goto(BASE_CHAT_URL);

		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		await input.fill("phân tích toàn diện UNI");
		await page.keyboard.press("Enter");

		await expect(page.getByText("coingecko.com")).toBeVisible({ timeout: 15_000 });
	});

	test("AC4: fact counter shows after fact-captured event", async ({ page, log }) => {
		await mockChatSSE(page, labSSE());
		await page.goto(BASE_CHAT_URL);

		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		await input.fill("phân tích toàn diện UNI");
		await page.keyboard.press("Enter");

		await expect(page.getByText(/1 facts captured/)).toBeVisible({ timeout: 15_000 });
	});

	test("AC9: model attribution badge renders", async ({ page, log }) => {
		await mockChatSSE(page, labSSE());
		await page.goto(BASE_CHAT_URL);

		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		await input.fill("phân tích toàn diện UNI");
		await page.keyboard.press("Enter");

		// Badge renders model short name + provider
		await expect(page.getByText(/sonnet-4-6.*trollllm/)).toBeVisible({ timeout: 15_000 });
	});

	test("AC12: rate-gate banner appears on rate-gate-wait event", async ({ page, log }) => {
		await mockChatSSE(page, labSSE());
		await page.goto(BASE_CHAT_URL);

		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		await input.fill("phân tích toàn diện UNI");
		await page.keyboard.press("Enter");

		const banner = page.locator('[data-slot="rate-gate-banner"]');
		await expect(banner).toBeVisible({ timeout: 15_000 });
		await expect(page.getByText(/7\.2/)).toBeVisible();
	});

	test("grid renders agent-grid slot for multi-agent session", async ({ page, log }) => {
		await mockChatSSE(page, multiAgentLabSSE());
		await page.goto(BASE_CHAT_URL);

		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		await input.fill("phân tích toàn diện UNI");
		await page.keyboard.press("Enter");

		const grid = page.locator('[data-slot="agent-grid"]');
		await expect(grid).toBeVisible({ timeout: 15_000 });

		// All 4 agent names visible in grid
		for (const name of ["Tokenomics Analyst", "DeFi Analyst", "Security Analyst", "News Analyst"]) {
			await expect(page.getByText(name).first()).toBeVisible();
		}
	});

	test("strip collapses to summary after completion", async ({ page, log }) => {
		await mockChatSSE(page, labSSE());
		await page.goto(BASE_CHAT_URL);

		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		await input.fill("phân tích toàn diện UNI");
		await page.keyboard.press("Enter");

		const strip = page.locator('[data-slot="orchestra-strip"]');
		await expect(strip).toHaveAttribute("data-variant", "collapsed", { timeout: 20_000 });
		await expect(page.getByText(/1\/1 done/)).toBeVisible();
	});
});
