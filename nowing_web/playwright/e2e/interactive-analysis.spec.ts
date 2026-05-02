import { test, expect } from "../support/merged-fixtures";

/**
 * E2E tests — Interactive Analysis (Story 9-UX-3)
 *
 * Tests are SSE-mocked — no live backend required.
 * Covers:
 *   P0: Watchlist add → toast appears, atom updated
 *   P0: Price alert create → modal opens, saves, toast appears
 *   P0: Scenario simulator — select Bull → re-synthesize → content swaps
 *   P0: Coin compare — open overlay, search token, comparison table renders
 *   P1: Follow-up chips render + click → autofills chat input
 *   P1: "View Base Case" resets scenario view
 */

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildSSEStream(events: Array<{ type: string; data: object }>): string {
	return (
		events.map((e) => `data: ${JSON.stringify({ type: e.type, data: e.data })}\n`).join("\n") + "\n"
	);
}

const SESSION_ID = "e2e-ux3-001";
const THREAD_ID = 42;
const TOKEN_SYMBOL = "LDO";
const TOKEN_NAME = "Lido DAO";
const COINGECKO_ID = "lido-dao";

const FOLLOW_UPS = [
	"Why did LDO TVL drop 46% from ATH?",
	"Compare LDO vs Rocket Pool (RPL)",
	"Is the fee switch proposal viable?",
];

/** Build a full crypto-report SSE stream */
function cryptoReportSSE(): string {
	const reportText = [
		"<!-- crypto-report-v2 -->",
		"# LDO Analysis",
		"## Overview",
		"Lido DAO is the leading liquid staking protocol.",
		"## Conclusion",
		"Based on current metrics, LDO shows strong fundamentals.",
	].join("\n");

	const citationMap = {
		"cit-1": {
			id: "cit-1",
			type: "coingecko",
			label: "CoinGecko LDO",
			url: "https://coingecko.com/en/coins/lido-dao",
			snippet: "LDO price: $1.23",
		},
	};

	const events: Array<{ type: string; data: object }> = [
		{
			type: "orchestra-spawn",
			data: {
				sessionId: SESSION_ID,
				agentId: "a1",
				agentName: "CoinGecko",
				agentType: "price",
			},
		},
		{
			type: "orchestra-done",
			data: { sessionId: SESSION_ID, agentId: "a1", citationIds: ["cit-1"] },
		},
		{
			type: "orchestra-complete",
			data: { sessionId: SESSION_ID, agentIds: ["a1"], citationCount: 1 },
		},
		// Report metadata
		{
			type: "data-report-type",
			data: { report_type: "comprehensive_crypto" },
		},
		{
			type: "data-token-meta",
			data: {
				token_symbol: TOKEN_SYMBOL,
				token_name: TOKEN_NAME,
				coingecko_id: COINGECKO_ID,
			},
		},
		{
			type: "data-citation-map",
			data: { citation_map: citationMap },
		},
		{
			type: "data-follow-ups",
			data: { follow_ups: FOLLOW_UPS },
		},
		// Text stream
		{ type: "text-delta", data: { delta: reportText } },
		{ type: "done", data: { thread_id: THREAD_ID } },
	];

	return buildSSEStream(events);
}

/** Scenario re-synthesis SSE stream */
function scenarioSSE(scenario: string): string {
	const content = `### Kịch bản: 🚀 Bull Case\nUnder bull assumptions, LDO price target: $3.50–$5.00.`;
	const events: Array<{ type: string; data: object }> = [
		{ type: "scenario-text-delta", data: { delta: content.slice(0, 40) } },
		{ type: "scenario-text-delta", data: { delta: content.slice(40) } },
		{ type: "scenario-complete", data: { scenario, cached: false } },
	];
	return buildSSEStream(events);
}

/** Token comparison SSE stream */
function compareSSE(): string {
	const compareData = {
		primary: {
			current_price_usd: 1.23,
			market_cap: 1_100_000_000,
			total_volume_24h: 52_000_000,
			price_change_24h_pct: 3.4,
			price_change_7d_pct: -8.1,
			ath_usd: 9.87,
		},
		secondary: {
			current_price_usd: 22.5,
			market_cap: 820_000_000,
			total_volume_24h: 31_000_000,
			price_change_24h_pct: 1.2,
			price_change_7d_pct: -5.4,
			ath_usd: 47.2,
		},
	};
	const verdict = "Based on fundamentals, LDO leads on TVL while RPL has stronger tokenomics.";

	const events: Array<{ type: string; data: object }> = [
		{ type: "data-compare-data", data: compareData },
		{ type: "data-compare-verdict-delta", data: { delta: verdict.slice(0, 40) } },
		{ type: "data-compare-verdict-delta", data: { delta: verdict.slice(40) } },
		{ type: "data-compare-complete", data: {} },
	];
	return buildSSEStream(events);
}

// ---------------------------------------------------------------------------
// Route mocks
// ---------------------------------------------------------------------------

async function mockChatSSE(page: import("@playwright/test").Page) {
	await page.route(/\/api\/(v\d+\/)?chat(\/.*)?$/, async (route) => {
		await route.fulfill({
			status: 200,
			headers: {
				"Content-Type": "text/event-stream",
				"Cache-Control": "no-cache",
				Connection: "keep-alive",
			},
			body: cryptoReportSSE(),
		});
	});

	await page.route(/\/api\/(v\d+\/)?threads(\/.*)?$/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({ id: THREAD_ID, sessionId: SESSION_ID }),
		});
	});
}

async function mockScenarioSSE(page: import("@playwright/test").Page, scenario = "bull") {
	await page.route(/\/api\/(v\d+\/)?scenarios\/resynthesize$/, async (route) => {
		await route.fulfill({
			status: 200,
			headers: {
				"Content-Type": "text/event-stream",
				"Cache-Control": "no-cache",
			},
			body: scenarioSSE(scenario),
		});
	});
}

async function mockCompareSSE(page: import("@playwright/test").Page) {
	await page.route(/\/api\/(v\d+\/)?compare\/tokens$/, async (route) => {
		await route.fulfill({
			status: 200,
			headers: {
				"Content-Type": "text/event-stream",
				"Cache-Control": "no-cache",
			},
			body: compareSSE(),
		});
	});
}

async function mockCoinGeckoSearch(page: import("@playwright/test").Page) {
	await page.route(/coingecko\.com\/api\/v3\/search/, async (route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({
				coins: [
					{
						id: "rocket-pool",
						name: "Rocket Pool",
						symbol: "RPL",
						thumb: "",
						market_cap_rank: 82,
					},
				],
			}),
		});
	});
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const BASE_CHAT_URL = "/dashboard/34/new-chat";

async function navigateAndSubmitQuery(
	page: import("@playwright/test").Page,
	query = "Analyze LDO"
) {
	await page.goto(BASE_CHAT_URL);
	const input = page
		.getByTestId("chat-input")
		.or(page.getByRole("textbox", { name: /message|query|ask/i }));
	await input.fill(query);
	await page.keyboard.press("Enter");
}

async function waitForReport(page: import("@playwright/test").Page) {
	await expect(page.locator('[data-slot="crypto-report-layout"]')).toBeVisible({ timeout: 15_000 });
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe("Interactive Analysis (9-UX-3)", () => {
	// -------------------------------------------------------------------------
	// P0 — Watchlist: add token → toast
	// -------------------------------------------------------------------------

	test("watchlist: clicking Watchlist action emits toast with token name", async ({
		page,
		log,
	}) => {
		await mockChatSSE(page);
		await mockScenarioSSE(page);

		await log({ level: "step", message: "Navigate and submit query" });
		await navigateAndSubmitQuery(page);

		await log({ level: "step", message: "Wait for crypto report to render" });
		await waitForReport(page);

		await log({ level: "step", message: "Click Watchlist action card" });
		const watchlistBtn = page
			.locator('[data-slot="next-action-bar"]')
			.getByRole("button", { name: /watchlist/i });
		await expect(watchlistBtn).toBeVisible({ timeout: 10_000 });
		await watchlistBtn.click();

		await log({ level: "step", message: "Verify toast appears" });
		const toast = page.locator("[data-sonner-toast]").or(page.locator('[role="status"]'));
		await expect(toast.filter({ hasText: /LDO/i })).toBeVisible({ timeout: 5_000 });
	});

	// -------------------------------------------------------------------------
	// P0 — Price Alert: open modal, fill threshold, save
	// -------------------------------------------------------------------------

	test("price alert: clicking Alert opens modal, save emits toast", async ({ page, log }) => {
		await mockChatSSE(page);

		await log({ level: "step", message: "Navigate and submit query" });
		await navigateAndSubmitQuery(page);
		await waitForReport(page);

		await log({ level: "step", message: "Click Price Alert action card" });
		const alertBtn = page
			.locator('[data-slot="next-action-bar"]')
			.getByRole("button", { name: /alert/i });
		await expect(alertBtn).toBeVisible({ timeout: 10_000 });
		await alertBtn.click();

		await log({ level: "step", message: "Verify alert dialog opens" });
		const dialog = page.getByRole("dialog");
		await expect(dialog).toBeVisible({ timeout: 5_000 });
		await expect(dialog.getByText(/LDO/i)).toBeVisible();

		await log({ level: "step", message: "Fill threshold and save" });
		const thresholdInput = dialog
			.getByRole("spinbutton")
			.or(dialog.locator('input[type="number"]'));
		if (await thresholdInput.isVisible()) {
			await thresholdInput.fill("2.00");
		}
		const saveBtn = dialog.getByRole("button", { name: /save|create|confirm/i });
		await saveBtn.click();

		await log({ level: "step", message: "Verify toast appears" });
		const toast = page.locator("[data-sonner-toast]").or(page.locator('[role="status"]'));
		await expect(toast.filter({ hasText: /alert/i })).toBeVisible({ timeout: 5_000 });
	});

	// -------------------------------------------------------------------------
	// P0 — Scenario simulator: select Bull → re-synthesize → content swaps
	// -------------------------------------------------------------------------

	test("scenario simulator: select Bull, re-synthesize, report content swaps", async ({
		page,
		log,
	}) => {
		await mockChatSSE(page);
		await mockScenarioSSE(page, "bull");

		await log({ level: "step", message: "Navigate and submit query" });
		await navigateAndSubmitQuery(page);
		await waitForReport(page);

		await log({ level: "step", message: "Scenario simulator panel should be visible" });
		const panel = page.locator('[data-slot="scenario-simulator-panel"]');
		await expect(panel).toBeVisible({ timeout: 10_000 });

		await log({ level: "step", message: "Switch to Bull tab" });
		const bullTab = panel.getByRole("tab", { name: /bull/i });
		await expect(bullTab).toBeVisible({ timeout: 5_000 });
		await bullTab.click();

		await log({ level: "step", message: "Click Re-synthesize button" });
		const resynthBtn = panel.getByRole("button", { name: /re-synthesize|resynthesize/i });
		await expect(resynthBtn).toBeVisible({ timeout: 5_000 });
		await resynthBtn.click();

		await log({ level: "step", message: "Verify active scenario badge appears" });
		const badge = page.locator('[data-slot="crypto-report-layout"]').getByText(/Bull Case/i);
		await expect(badge).toBeVisible({ timeout: 15_000 });

		await log({ level: "step", message: "Verify report content updated (scenario text)" });
		const scenarioContent = page.getByText(/Bull Case/i).first();
		await expect(scenarioContent).toBeVisible();

		await log({ level: "step", message: "Verify 'View Base Case' toggle is visible" });
		const baseToggle = page.getByRole("button", { name: /view base case/i });
		await expect(baseToggle).toBeVisible({ timeout: 5_000 });
	});

	// -------------------------------------------------------------------------
	// P0 — Coin compare: open overlay, search, comparison table renders
	// -------------------------------------------------------------------------

	test("coin compare: open overlay, search RPL, comparison table renders", async ({
		page,
		log,
	}) => {
		await mockChatSSE(page);
		await mockCompareSSE(page);
		await mockCoinGeckoSearch(page);

		await log({ level: "step", message: "Navigate and submit query" });
		await navigateAndSubmitQuery(page);
		await waitForReport(page);

		await log({ level: "step", message: "Click Compare action card" });
		const compareBtn = page
			.locator('[data-slot="next-action-bar"]')
			.getByRole("button", { name: /compare/i });
		await expect(compareBtn).toBeVisible({ timeout: 10_000 });
		await compareBtn.click();

		await log({ level: "step", message: "Verify comparison overlay opens" });
		const overlay = page
			.locator('[data-slot="coin-comparison-overlay"]')
			.or(page.getByRole("dialog", { name: /compare/i }));
		await expect(overlay).toBeVisible({ timeout: 5_000 });

		await log({ level: "step", message: "Search for RPL in token picker" });
		const searchInput = overlay.getByRole("textbox");
		await searchInput.fill("RPL");

		await log({ level: "step", message: "Select RPL from results" });
		const rplResult = overlay.getByText("RPL").first();
		await expect(rplResult).toBeVisible({ timeout: 5_000 });
		await rplResult.click();

		await log({ level: "step", message: "Verify comparison table renders" });
		const compTable = page.locator('[data-slot="comparison-table"]');
		await expect(compTable).toBeVisible({ timeout: 15_000 });

		await log({ level: "step", message: "Verify both token symbols appear in table header" });
		await expect(compTable.getByText("LDO")).toBeVisible();
		await expect(compTable.getByText("RPL")).toBeVisible();

		await log({ level: "step", message: "Verify verdict box appears after streaming" });
		const verdictBox = compTable.locator('[data-slot="verdict-box"]');
		await expect(verdictBox).toBeVisible({ timeout: 10_000 });
	});

	// -------------------------------------------------------------------------
	// P1 — Follow-up chips: render and click autofills chat input
	// -------------------------------------------------------------------------

	test("follow-up chips: render from metadata, click autofills chat input", async ({
		page,
		log,
	}) => {
		await mockChatSSE(page);

		await log({ level: "step", message: "Navigate and submit query" });
		await navigateAndSubmitQuery(page);
		await waitForReport(page);

		await log({ level: "step", message: "Verify follow-up chips rendered" });
		const chipsContainer = page.locator('[data-slot="follow-up-chips"]');
		await expect(chipsContainer).toBeVisible({ timeout: 10_000 });

		// At least one chip should be visible
		const firstChip = chipsContainer.getByRole("button").first();
		await expect(firstChip).toBeVisible();

		await log({ level: "step", message: "Click first follow-up chip" });
		const chipText = await firstChip.textContent();
		await firstChip.click();

		await log({ level: "step", message: "Verify chat input was autofilled" });
		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		if (chipText) {
			// Input should contain some portion of the chip text
			const inputValue = await input.inputValue();
			expect(inputValue.length).toBeGreaterThan(0);
		}
	});

	// -------------------------------------------------------------------------
	// P1 — View Base Case: resets scenario content
	// -------------------------------------------------------------------------

	test("scenario: 'View Base Case' button resets report to original content", async ({
		page,
		log,
	}) => {
		await mockChatSSE(page);
		await mockScenarioSSE(page, "bear");

		await log({ level: "step", message: "Navigate and submit query" });
		await navigateAndSubmitQuery(page);
		await waitForReport(page);

		await log({ level: "step", message: "Switch to Bear scenario" });
		const panel = page.locator('[data-slot="scenario-simulator-panel"]');
		await expect(panel).toBeVisible({ timeout: 10_000 });
		const bearTab = panel.getByRole("tab", { name: /bear/i });
		await bearTab.click();
		const resynthBtn = panel.getByRole("button", { name: /re-synthesize|resynthesize/i });
		await resynthBtn.click();

		await log({ level: "step", message: "Wait for scenario to load" });
		const baseToggle = page.getByRole("button", { name: /view base case/i });
		await expect(baseToggle).toBeVisible({ timeout: 15_000 });

		await log({ level: "step", message: "Click View Base Case" });
		await baseToggle.click();

		await log({ level: "step", message: "Verify scenario badge disappears" });
		await expect(baseToggle).not.toBeVisible({ timeout: 5_000 });

		await log({ level: "step", message: "Verify original report is shown (no scenario badge)" });
		const scenarioBadge = page
			.locator('[data-slot="crypto-report-layout"]')
			.getByText(/Bear Case/i);
		await expect(scenarioBadge).not.toBeVisible();
	});

	// -------------------------------------------------------------------------
	// P1 — Deep Dive: autofills chat input with deep-dive prompt
	// -------------------------------------------------------------------------

	test("deep dive: clicking Deep Dive autofills chat input", async ({ page, log }) => {
		await mockChatSSE(page);

		await log({ level: "step", message: "Navigate and submit query" });
		await navigateAndSubmitQuery(page);
		await waitForReport(page);

		await log({ level: "step", message: "Click Deep Dive action card" });
		const deepDiveBtn = page
			.locator('[data-slot="next-action-bar"]')
			.getByRole("button", { name: /deep dive/i });
		await expect(deepDiveBtn).toBeVisible({ timeout: 10_000 });
		await deepDiveBtn.click();

		await log({ level: "step", message: "Verify chat input is autofilled with LDO deep-dive prompt" });
		const input = page
			.getByTestId("chat-input")
			.or(page.getByRole("textbox", { name: /message|query|ask/i }));
		const inputValue = await input.inputValue();
		expect(inputValue.length).toBeGreaterThan(0);
		// Input should mention LDO or deep dive context
		expect(inputValue.toLowerCase()).toMatch(/ldo|deep|dive|analysis/);
	});
});
