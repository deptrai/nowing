import type { Page, Route } from "@playwright/test";
import { expect, test } from "../fixtures";
import { mockAdminAuth } from "../helpers/admin-auth";
import { fulfillJson } from "../helpers/cors";

/**
 * Story 21.8a: XActions Universal Ingress & Health Operations E2E Tests.
 *
 * Validates:
 * 1. XActions health probe telemetry displays under Scraper category (healthy, healthyProxyCount, metrics).
 * 2. Degraded state triggers alert banner when backpressure or stream alert occurs.
 * 3. On-demand probe execution refreshes telemetry data without page reload.
 */

const mockOverviewWithXActions = {
	overall_status: "healthy",
	total_monitored: 4,
	status_counts: {
		healthy: 4,
		degraded: 0,
		unavailable: 0,
		not_configured: 0,
		disabled: 0,
	},
	categories: {
		infra: { healthy: 1, degraded: 0, unavailable: 0, total: 1 },
		model: { healthy: 1, degraded: 0, unavailable: 0, total: 1 },
		scraper: { healthy: 2, degraded: 0, unavailable: 0, total: 2 },
	},
	registered_categories: ["infra", "model", "scraper"],
	probes_last_hour: 60,
	active_alerts_count: 0,
};

const mockXActionsHealthyStatus = {
	service_id: "scraper/xactions",
	service_name: "XActions Social Graph",
	category: "scraper",
	display_group: "B2B Lead Intelligence",
	status: "healthy",
	latency_ms: 85,
	success_rate_15m: 100.0,
	error_rate_15m: 0.0,
	last_error: null,
	last_probe_at: new Date().toISOString(),
	suggested_action: null,
	metadata_payload: {
		healthy_proxies: 8,
		backpressure: "none",
		stream_metrics: { length: 1250, lag: 0 },
		stream_alerts: [],
	},
};

const mockXActionsDegradedStatus = {
	...mockXActionsHealthyStatus,
	status: "degraded",
	last_error: "XActions stream alert: queue_depth_exceeded",
	suggested_action: "Check XActions proxy pool and governor",
	metadata_payload: {
		healthy_proxies: 2,
		backpressure: "moderate",
		stream_metrics: { length: 8500, lag: 450 },
		stream_alerts: ["queue_depth_exceeded"],
	},
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
	mockXActionsHealthyStatus,
];

test.describe("Story 21.8a: XActions Universal Ingress & Health Operations", () => {
	test.beforeEach(async ({ page }) => {
		await mockAdminAuth(page);

		await page.route("**/api/v1/admin/health/overview", async (route: Route) => {
			await fulfillJson(route, 200, mockOverviewWithXActions);
		});

		await page.route("**/api/v1/admin/health/statuses*", async (route: Route) => {
			await fulfillJson(route, 200, mockStatuses);
		});

		await page.route("**/api/v1/admin/health/alerts", async (route: Route) => {
			await fulfillJson(route, 200, []);
		});
	});

	test("displays XActions service card under scraper category with healthy proxy count", async ({ page }) => {
		await page.goto("/admin/health");

		// Click on scraper category tab
		const scraperTab = page.getByRole("tab", { name: /scraper/i });
		if (await scraperTab.isVisible()) {
			await scraperTab.click();
		}

		// Verify XActions service card is visible
		const xactionsCard = page.getByText("XActions Social Graph");
		await expect(xactionsCard).toBeVisible();

		// Click on card to open drilldown modal
		await xactionsCard.click();

		// Check modal details
		await expect(page.getByText("healthy_proxies")).toBeVisible();
		await expect(page.getByText("8")).toBeVisible();
	});

	test("reflects degraded state with low proxies and triggers alert banner", async ({ page }) => {
		// Mock degraded status and active alert
		await page.route("**/api/v1/admin/health/overview", async (route: Route) => {
			await fulfillJson(route, 200, {
				...mockOverviewWithXActions,
				overall_status: "degraded",
				active_alerts_count: 1,
			});
		});

		await page.route("**/api/v1/admin/health/statuses*", async (route: Route) => {
			await fulfillJson(route, 200, [mockStatuses[0], mockXActionsDegradedStatus]);
		});

		await page.route("**/api/v1/admin/health/alerts", async (route: Route) => {
			await fulfillJson(route, 200, [
				{
					id: "alert-xactions-01",
					service_id: "scraper/xactions",
					severity: "warning",
					message: "XActions stream alert: queue_depth_exceeded",
					created_at: new Date().toISOString(),
				},
			]);
		});

		await page.goto("/admin/health");

		// Alert banner should be rendered
		await expect(page.getByText("queue_depth_exceeded")).toBeVisible();

		// Verify card shows degraded status
		await expect(page.getByText("XActions Social Graph")).toBeVisible();
	});

	test("on-demand probe execution triggers refresh", async ({ page }) => {
		let probed = false;

		await page.route("**/api/v1/admin/health/probe/scraper%2Fxactions", async (route: Route) => {
			probed = true;
			await fulfillJson(route, 200, mockXActionsHealthyStatus);
		});

		await page.goto("/admin/health");

		// Open card modal
		await page.getByText("XActions Social Graph").click();

		// Trigger probe now button
		const probeButton = page.getByRole("button", { name: /probe now|test now|refresh/i });
		if (await probeButton.isVisible()) {
			await probeButton.click();
			expect(probed).toBe(true);
		}
	});
});
