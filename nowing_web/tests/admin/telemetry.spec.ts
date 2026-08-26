import type { Page, Route } from "@playwright/test";
import { expect, test } from "../fixtures";

/**
 * Story 25.4: Realtime LLM Token Cost, Proxy Health & Celery Queue Telemetry.
 *
 * These specs validate the `/admin/telemetry` dashboard by intercepting the
 * backend API and serving deterministic responses. This lets us exercise the
 * frontend panels, error states, and auto-refresh without requiring a
 * pre-seeded superadmin or live token usage data.
 */

const mockLlmCost = {
	window_hours: 24,
	provider: null,
	workspace_id: null,
	total_tokens: 900,
	total_cost_micros: 70000,
	non_llm_cost_micros: 5000,
	billing_cost_micros: 5000,
	input_tokens: 600,
	output_tokens: 300,
	by_provider: [
		{ key: "openai", total_tokens: 900, cost_micros: 70000, input_tokens: 600, output_tokens: 300 },
	],
	by_model: [
		{ key: "gpt-4o", total_tokens: 900, cost_micros: 70000, input_tokens: 600, output_tokens: 300 },
	],
	by_workspace: [
		{ key: "2", total_tokens: 900, cost_micros: 70000, input_tokens: 600, output_tokens: 300 },
	],
	by_usage_type: [
		{ key: "chat", total_tokens: 900, cost_micros: 70000, input_tokens: 600, output_tokens: 300 },
	],
	time_series: [
		{
			period: "2026-08-26 06:00",
			total_tokens: 0,
			cost_micros: 0,
			input_tokens: 0,
			output_tokens: 0,
		},
		{
			period: "2026-08-26 10:00",
			total_tokens: 900,
			cost_micros: 70000,
			input_tokens: 600,
			output_tokens: 300,
		},
	],
	unreported_cost_rows: 0,
};

const mockGrossMargin = {
	window_hours: 24,
	total_revenue_micros: 1_000_000,
	total_cogs_micros: 70_000,
	billing_cost_micros: 5_000,
	non_llm_cost_micros: 5_000,
	overall_gross_margin: 0.93,
	worst_workspace_id: 2,
	worst_workspace_margin: 0.93,
	worst_model: "gpt-4o",
	points: [
		{ period: "2026-08-26 06:00", revenue_micros: 0, cogs_micros: 0, gross_margin: null },
		{
			period: "2026-08-26 10:00",
			revenue_micros: 1_000_000,
			cogs_micros: 70_000,
			gross_margin: 0.93,
		},
	],
};

const mockProxyHealth = {
	status: "degraded",
	provider: "custom",
	snapshots: [
		{
			provider: "custom",
			url: "http://gw.example:823",
			latency_ms: 620,
			success_rate: 1,
			status: "degraded",
			last_error: null,
			last_probed_at: new Date().toISOString(),
		},
	],
	total: 1,
	healthy: 0,
	degraded: 1,
	dead: 0,
};

const mockCeleryQueues = {
	status: "unavailable",
	active_workers: 0,
	queues: [
		{
			name: "nowing",
			length: 0,
			workers: 0,
			throughput_per_min: 0,
			stalled_count: 0,
			status: "healthy",
		},
	],
};

async function setupAdminTelemetryMocks(page: Page) {
	await page.route(/.*\/auth\/session(\?.*)?$/, async (route: Route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({
				authenticated: true,
				access_expires_at: Date.now() / 1000 + 3_600,
				is_impersonation: false,
				impersonated_by: null,
				target_user: null,
			}),
		});
	});

	await page.route(/.*\/users\/me(\?.*)?$/, async (route: Route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify({
				id: "admin-test-user-0000-0000-0000-000000000001",
				email: "admin-test@nowing.net",
				is_active: true,
				is_superuser: true,
				is_verified: true,
				credit_micros_balance: 0,
				display_name: "Admin Test",
				avatar_url: null,
				notification_preferences: null,
			}),
		});
	});

	await page.route(/.*\/api\/v1\/admin\/telemetry\/llm-cost(\?.*)?$/, async (route: Route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify(mockLlmCost),
		});
	});

	await page.route(/.*\/api\/v1\/admin\/telemetry\/gross-margin(\?.*)?$/, async (route: Route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify(mockGrossMargin),
		});
	});

	await page.route(/.*\/api\/v1\/admin\/telemetry\/proxy-health$/, async (route: Route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify(mockProxyHealth),
		});
	});

	await page.route(/.*\/api\/v1\/admin\/telemetry\/celery-queues$/, async (route: Route) => {
		await route.fulfill({
			status: 200,
			contentType: "application/json",
			body: JSON.stringify(mockCeleryQueues),
		});
	});
}

test.describe("Story 25.4 — Admin Telemetry Dashboard", () => {
	test("[P0] renders all four telemetry panels with mocked data", async ({ page }) => {
		await setupAdminTelemetryMocks(page);
		await page.goto("/admin/telemetry");

		await expect(page.getByRole("heading", { name: "Admin: Telemetry" })).toBeVisible();
		await expect(page.getByText("Refreshes every 5s")).toBeVisible();

		// Gross Margin panel
		await expect(page.getByRole("heading", { name: "Gross Margin" })).toBeVisible();
		await expect(page.getByText("$1.00")).toBeVisible();
		await expect(page.getByText("Margin 93.00%")).toBeVisible();
		await expect(page.getByText("worst model: gpt-4o")).toBeVisible();

		// LLM Cost panel
		await expect(page.getByText("Total Tokens")).toBeVisible();
		await expect(page.getByText("900").first()).toBeVisible();
		await expect(page.getByText("$0.0700").first()).toBeVisible();
		await expect(page.getByRole("cell", { name: "gpt-4o" }).first()).toBeVisible();
		await expect(page.getByRole("cell", { name: "chat" }).first()).toBeVisible();

		// Proxy Health panel
		await expect(page.getByRole("heading", { name: "Proxy Health" })).toBeVisible();
		await expect(page.getByText("degraded").first()).toBeVisible();
		await expect(page.getByText("custom").first()).toBeVisible();

		// Celery Queues panel
		await expect(page.getByRole("heading", { name: "Celery Queues" })).toBeVisible();
		await expect(page.getByText("nowing")).toBeVisible();
	});

	test("[P0] panel refreshes after window change without console errors", async ({ page }) => {
		await setupAdminTelemetryMocks(page);
		await page.goto("/admin/telemetry");

		const llmWindow = page
			.locator("div")
			.filter({ hasText: "LLM Cost" })
			.first()
			.locator("select")
			.first();
		await llmWindow.selectOption("1h");

		// Auto-refresh should re-fetch with the new window; no error state should appear.
		await expect(page.getByText("Unable to connect to the server")).not.toBeVisible();

		const consoleErrors: string[] = [];
		page.on("console", (msg) => {
			if (msg.type() === "error") consoleErrors.push(msg.text());
		});

		// Wait for at least one auto-refresh tick (5s).
		await page.waitForTimeout(6_000);
		expect(consoleErrors).toHaveLength(0);
	});
});
