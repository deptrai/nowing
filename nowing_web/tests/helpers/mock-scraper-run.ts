import type { Page, Route } from "@playwright/test";

/**
 * Mocks the async scraper-run flow used by `useRunStream` /
 * `scrapersApiService.runAsync`:
 *
 *   1. POST /workspaces/{id}/scrapers/{platform}/{verb}?mode=async → 202 {run_id}
 *   2. GET  /workspaces/{id}/scrapers/runs/{run_id}/events (SSE)  → run.finished
 *   3. GET  /workspaces/{id}/scrapers/runs/{run_id}               → run detail
 *
 * `payload` becomes the run's `output_text` (stringified).
 * Register this BEFORE navigating; Playwright matches the last-registered
 * route first, so tests can re-mock with a different payload per test.
 */
export async function mockScraperRun(
	page: Page,
	options: {
		platform: string;
		verb: string;
		payload: Record<string, unknown>;
		input?: Record<string, unknown>;
		itemCount?: number;
	}
) {
	const { platform, verb, payload, input = {}, itemCount = 1 } = options;
	const id = `run-${platform}-mock-${Math.floor(Math.random() * 1e6)}`;

	await page.route("**/api/v1/**", async (route: Route) => {
		const req = route.request();
		const url = req.url();

		if (url.includes(`/scrapers/${platform}/${verb}?mode=async`) && req.method() === "POST") {
			await route.fulfill({
				status: 202,
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ run_id: id, status: "running" }),
			});
			return;
		}

		if (url.includes(`/scrapers/runs/${id}/events`) && req.method() === "GET") {
			const accept = req.headers().accept || "";
			if (accept.includes("text/event-stream")) {
				const sseBody = `data: ${JSON.stringify({ type: "run.started", run_id: id, status: "running" })}\n\ndata: ${JSON.stringify({ type: "run.finished", run_id: id, status: "success" })}\n\n`;
				await route.fulfill({
					status: 200,
					headers: { "Content-Type": "text/event-stream" },
					body: sseBody,
				});
				return;
			}
		}

		if (
			url.includes(`/scrapers/runs/${id}`) &&
			req.method() === "GET" &&
			!url.includes("/events")
		) {
			await route.fulfill({
				status: 200,
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					id,
					capability: `${platform}.${verb}`,
					origin: "ui",
					status: "success",
					item_count: itemCount,
					char_count: JSON.stringify(payload).length,
					duration_ms: 1000,
					cost_micros: 0,
					error: null,
					created_at: new Date().toISOString(),
					thread_id: null,
					input,
					output_text: JSON.stringify(payload),
					progress: [],
				}),
			});
			return;
		}

		await route.continue();
	});
}
