import type { Page, Route } from "@playwright/test";
import { expect, test } from "../fixtures";
import { mockAdminAuth } from "../helpers/admin-auth";
import { fulfillJson } from "../helpers/cors";

/**
 * Story 25.7: Third-Party Health & Operations Dashboard E2E Tests.
 *
 * Validates:
 * 1. Health dashboard renders active alert banner, 5-col overview grid, category tabs, and status cards.
 * 2. Category tab switching filters displayed services.
 * 3. Acknowledging an alert removes it from the banner.
 * 4. Clicking a service card opens the drill-down modal with probe history and on-demand probe action.
 */

const mockOverview = {
	overall_status: "degraded",
	total_monitored: 3,
	status_counts: {
		healthy: 1,
		degraded: 1,
		unavailable: 1,
		not_configured: 0,
		disabled: 0,
	},
	categories: {
		infra: { healthy: 1, degraded: 0, unavailable: 0, total: 1 },
		model: { healthy: 0, degraded: 1, unavailable: 0, total: 1 },
		scraper: { healthy: 0, degraded: 0, unavailable: 1, total: 1 },
	},
	registered_categories: ["infra", "model", "scraper"],
	probes_last_hour: 45,
	active_alerts_count: 1,
};

const mockStatuses = [
	{
		service_id: "infra/postgres",
		service_name: "PostgreSQL Database",
		category: "infra",
		display_group: "Infrastructure",
		status: "healthy",
		latency_ms: 12,
		success_rate_15m: 100.0,
		error_rate_15m: 0.0,
		last_error: null,
		last_probe_at: new Date().toISOString(),
		suggested_action: null,
		metadata_payload: { pool_size: 10 },
	},
	{
		service_id: "model/gpt-5",
		service_name: "OpenAI GPT-5",
		category: "model",
		display_group: "LLM Models",
		status: "degraded",
		latency_ms: 1250,
		success_rate_15m: 85.0,
		error_rate_15m: 15.0,
		last_error: "Latency high > 1000ms",
		last_probe_at: new Date().toISOString(),
		suggested_action: "Monitor error rates",
		metadata_payload: { provider: "openai" },
	},
	{
		service_id: "scraper/tiktok",
		service_name: "TikTok Scraper",
		category: "scraper",
		display_group: "Scrapers",
		status: "unavailable",
		latency_ms: null,
		success_rate_15m: 0.0,
		error_rate_15m: 100.0,
		last_error: "Upstream rate limited (429)",
		last_probe_at: new Date().toISOString(),
		suggested_action: "Rotate proxy endpoints",
		metadata_payload: { capability_id: "scraper.tiktok" },
	},
];

const mockAlerts = [
	{
		id: 42,
		service_id: "scraper/tiktok",
		rule_id: 1,
		severity: "critical",
		message: "TikTok Scraper is unavailable: 2 consecutive failures",
		status: "open",
		created_at: new Date().toISOString(),
		acknowledged_until: null,
	},
];

const mockHistory = [
	{
		id: 101,
		service_id: "infra/postgres",
		status: "healthy",
		latency_ms: 12,
		error_message: null,
		probe_at: new Date(Date.now() - 60000).toISOString(),
	},
	{
		id: 100,
		service_id: "infra/postgres",
		status: "healthy",
		latency_ms: 15,
		error_message: null,
		probe_at: new Date(Date.now() - 120000).toISOString(),
	},
];

async function setupAdminHealthMocks(page: Page) {
	await mockAdminAuth(page);

	let currentAlerts = [...mockAlerts];

	// Mock overview
	await page.route(/.*\/api\/v1\/admin\/telemetry\/health\/overview$/, async (route: Route) => {
		await fulfillJson(route, 200, mockOverview);
	});

	// Mock alerts
	await page.route(/.*\/api\/v1\/admin\/telemetry\/health\/alerts$/, async (route: Route) => {
		await fulfillJson(route, 200, { items: currentAlerts, total: currentAlerts.length });
	});

	// Mock acknowledge
	await page.route(
		/.*\/api\/v1\/admin\/telemetry\/health\/alerts\/(\d+)\/acknowledge$/,
		async (route: Route) => {
			const match = route
				.request()
				.url()
				.match(/\/alerts\/(\d+)\/acknowledge/);
			const alertId = match ? Number.parseInt(match[1], 10) : 42;
			currentAlerts = currentAlerts.filter((a) => a.id !== alertId);
			await fulfillJson(route, 200, { ...mockAlerts[0], id: alertId, status: "acknowledged" });
		}
	);

	// Mock statuses with query filtering
	await page.route(
		/.*\/api\/v1\/admin\/telemetry\/health\/statuses(\?.*)?$/,
		async (route: Route) => {
			const url = new URL(route.request().url());
			const cat = url.searchParams.get("category");
			const filtered = cat ? mockStatuses.filter((s) => s.category === cat) : mockStatuses;
			await fulfillJson(route, 200, { items: filtered, total: filtered.length });
		}
	);

	// Mock history
	await page.route(/.*\/api\/v1\/admin\/telemetry\/health\/history\/.*$/, async (route: Route) => {
		await fulfillJson(route, 200, { items: mockHistory, total: mockHistory.length });
	});

	// Mock on-demand probe
	await page.route(/.*\/api\/v1\/admin\/telemetry\/health\/probe\/.*$/, async (route: Route) => {
		await fulfillJson(route, 200, {
			service_id: "infra/postgres",
			status: "healthy",
			latency_ms: 10,
			last_error: null,
			probed_at: new Date().toISOString(),
		});
	});
}

test.describe("Story 25.7 — Admin Health & Operations Dashboard", () => {
	test("[P0] renders dashboard overview, alert banner, and status cards", async ({ page }) => {
		await setupAdminHealthMocks(page);
		await page.goto("/admin/telemetry");

		// Header & Tab triggers
		await expect(
			page.getByRole("heading", { name: "Admin: Operations & Telemetry" })
		).toBeVisible();
		await expect(page.getByTestId("tab-trigger-health")).toBeVisible();
		await expect(page.getByTestId("tab-trigger-telemetry")).toBeVisible();

		// Active alert banner
		await expect(page.getByTestId("health-alert-banner")).toBeVisible();
		await expect(page.getByText("TikTok Scraper is unavailable")).toBeVisible();
		await expect(page.getByText("CRITICAL")).toBeVisible();

		// Status cards grid
		await expect(page.getByTestId("health-card-infra/postgres")).toBeVisible();
		await expect(page.getByTestId("health-card-model/gpt-5")).toBeVisible();
		await expect(page.getByTestId("health-card-scraper/tiktok")).toBeVisible();
	});

	test("[P0] category tabs switch and filter services correctly", async ({ page }) => {
		await setupAdminHealthMocks(page);
		await page.goto("/admin/telemetry");

		// Switch to "Infrastructure"
		const infraTab = page.getByTestId("tab-category-infra");
		await expect(infraTab).toBeVisible();
		await infraTab.click();

		// Should show only Postgres
		await expect(page.getByTestId("health-card-infra/postgres")).toBeVisible();
		await expect(page.getByTestId("health-card-model/gpt-5")).not.toBeVisible();
		await expect(page.getByTestId("health-card-scraper/tiktok")).not.toBeVisible();

		// Switch to "AI Models"
		const modelTab = page.getByTestId("tab-category-model");
		await expect(modelTab).toBeVisible();
		await modelTab.click();

		// Should show only GPT-5
		await expect(page.getByTestId("health-card-model/gpt-5")).toBeVisible();
		await expect(page.getByTestId("health-card-infra/postgres")).not.toBeVisible();
	});

	test("[P0] acknowledge alert snoozes and hides banner", async ({ page }) => {
		await setupAdminHealthMocks(page);
		await page.goto("/admin/telemetry");

		// Alert banner has acknowledge button
		const ackBtn = page.getByTestId("acknowledge-alert-42");
		await expect(ackBtn).toBeVisible();
		await ackBtn.click();

		// Alert banner should be removed
		await expect(page.getByTestId("health-alert-banner")).not.toBeVisible();
	});

	test("[P0] service card click opens drill-down modal with test now action", async ({ page }) => {
		await setupAdminHealthMocks(page);
		await page.goto("/admin/telemetry");

		// Click on postgres card
		const postgresCard = page.getByTestId("health-card-infra/postgres");
		await postgresCard.click();

		// Modal opens
		const modal = page.getByTestId("health-drilldown-modal");
		await expect(modal).toBeVisible();
		await expect(modal.getByText("PostgreSQL Database")).toBeVisible();
		await expect(modal.getByText("24-Hour Probe History")).toBeVisible();

		// On-demand probe button
		const testNowBtn = page.getByTestId("btn-run-probe");
		await expect(testNowBtn).toBeVisible();
		await testNowBtn.click();

		// After probe, probe completed text should appear
		await expect(page.getByText("Test Probe Completed")).toBeVisible();
	});
});
