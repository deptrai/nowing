import { expect, test } from "@playwright/test";

/**
 * Story 29.2: Workspace Health & Adoption Analytics Dashboard
 * Governed by: AC-1 through AC-6, AD-52, INV-29.3, HD-1 through HD-5
 */

const mockSummaryFull = {
	workspace_id: 1,
	date_range: "30d",
	start_date: "2026-08-08",
	end_date: "2026-09-07",
	is_public_snapshot: false,
	active_members_dau: {
		current_value: 12,
		change_pct: 15.4,
		sparkline: [8, 9, 10, 10, 11, 11, 12, 12, 11, 12, 13, 12, 12, 12],
	},
	active_members_wau: {
		current_value: 45,
		change_pct: 8.2,
		sparkline: [35, 36, 38, 40, 42, 43, 44, 45, 45, 45, 44, 45, 45, 45],
	},
	total_members: {
		current_value: 12,
		change_pct: 0,
		sparkline: [12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12],
	},
	total_memories: {
		current_value: 1420,
		change_pct: 22.5,
		sparkline: [1100, 1150, 1200, 1250, 1300, 1320, 1350, 1380, 1400, 1410, 1420],
	},
	memory_growth_count: {
		current_value: 320,
		change_pct: 12.0,
		sparkline: [20, 22, 25, 21, 28, 30, 26, 29, 31, 35, 32, 30, 28, 32],
	},
	query_volume: {
		current_value: 580,
		change_pct: 18.3,
		sparkline: [30, 35, 40, 38, 45, 42, 48, 50, 52, 55, 53, 56, 58, 60],
	},
	recall_queries: 420,
	remember_queries: 60,
	research_queries: 100,
	credits_consumed_micros: {
		current_value: 85000000,
		change_pct: 5.5,
		sparkline: [5000000, 6000000, 7000000, 7500000, 8000000, 8500000],
	},
	cost_per_turn_micros: {
		current_value: 45000,
		change_pct: -3.2,
		sparkline: [50000, 48000, 47000, 46000, 45500, 45000],
	},
	top_sources: [
		{
			source_type: "document",
			memory_count: 850,
			query_count: 320,
			cost_micros: 42000000,
		},
		{
			source_type: "slack_connector",
			memory_count: 420,
			query_count: 180,
			cost_micros: 28000000,
		},
		{
			source_type: "google_drive",
			memory_count: 150,
			query_count: 80,
			cost_micros: 15000000,
		},
	],
	source_coverage_gap_count: 1,
	quota_progress: [
		{
			metric: "memory_count",
			label: "Memory Capacity",
			current_value: 850,
			limit_value: 1000,
			utilization_pct: 85.0,
			status: "warning",
			recommended_tier: "Team",
		},
		{
			metric: "monthly_credits",
			label: "Monthly Credits",
			current_value: 52500000,
			limit_value: 50000000,
			utilization_pct: 105.0,
			status: "alert",
			recommended_tier: "Enterprise",
		},
		{
			metric: "storage_bytes",
			label: "Storage Allocation",
			current_value: 25000000,
			limit_value: 100000000,
			utilization_pct: 25.0,
			status: "normal",
			recommended_tier: null,
		},
	],
	daily_metrics: [
		{
			date: "2026-09-06",
			active_members_dau: 12,
			active_members_wau: 45,
			total_memories: 1420,
			memory_growth_count: 32,
			recall_queries: 40,
			remember_queries: 5,
			research_queries: 10,
			query_volume: 55,
			credits_consumed_micros: 85000000,
			cost_per_turn_micros: 45000,
		},
	],
};

const mockGaps = {
	gaps: [
		{
			source_type: "google_drive",
			enabled_since: "2026-07-01T00:00:00Z",
			last_synced_at: null,
			remediation_action: "Trigger manual sync or verify connector credentials",
			configure_url: "/dashboard/1/connectors",
		},
	],
	total_gaps: 1,
};

const mockSourceDrilldown = {
	workspace_id: 1,
	source_type: "document",
	total_memories: 850,
	query_volume: 320,
	cost_micros: 42000000,
	recent_samples: [
		{
			id: 101,
			content: "Quarterly product roadmap meeting minutes and action items.",
			created_at: "2026-09-06T14:30:00Z",
			confidence: 0.95,
			tags: ["roadmap", "strategy"],
		},
		{
			id: 102,
			content: "Engineering sprint retrospective notes on vector search latency.",
			created_at: "2026-09-05T11:20:00Z",
			confidence: 0.92,
			tags: ["engineering", "performance"],
		},
	],
};

test.describe("Story 29.2: Workspace Health & Adoption Analytics Dashboard", () => {
	test.beforeEach(async ({ page }) => {
		// Mock member access permissions (Full Owner access)
		await page.route("**/api/v1/workspaces/1/members/my-access", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					is_owner: true,
					permissions: ["*"],
				}),
			});
		});

		// Mock coverage gaps
		await page.route("**/api/v1/workspaces/1/health/coverage-gaps", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(mockGaps),
			});
		});

		// Mock source drilldown
		await page.route("**/api/v1/workspaces/1/health/sources/*", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(mockSourceDrilldown),
			});
		});

		// Mock health summary default
		await page.route("**/api/v1/workspaces/1/health?*", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(mockSummaryFull),
			});
		});
		await page.route("**/api/v1/workspaces/1/health", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(mockSummaryFull),
			});
		});
	});

	test("HD-1: renders all metric cards with sparklines and 7-day change badges", async ({
		page,
	}) => {
		await page.goto("/dashboard/1/health");

		// Header verification
		await expect(page.getByRole("heading", { name: "Workspace Health & Adoption" })).toBeVisible();

		// Metric Cards
		await expect(page.getByText("Active Members")).toBeVisible();
		await expect(page.getByText("Total Members")).toBeVisible();
		await expect(page.getByText("Total Memories")).toBeVisible();
		await expect(page.getByText("Memory Growth Rate")).toBeVisible();
		await expect(page.getByText("Query Volume")).toBeVisible();
		await expect(page.getByText("Credits Consumed")).toBeVisible();
		await expect(page.getByText("Cost Per Turn")).toBeVisible();

		// Metric Values
		await expect(page.getByText("1.4K")).toBeVisible(); // Total memories formatted compact
		await expect(page.getByText("+320")).toBeVisible(); // Memory growth
		await expect(page.getByText("580")).toBeVisible(); // Query volume
		await expect(page.getByText("$85.00")).toBeVisible(); // 85M micros
		await expect(page.getByText("$0.04")).toBeVisible(); // 45k micros / 1M = $0.045

		// Sparklines render as SVG elements
		const sparklines = page.locator("svg");
		expect(await sparklines.count()).toBeGreaterThan(5);

		// 7-day change badges
		await expect(page.getByText("+15.4% (7d)")).toBeVisible();
		await expect(page.getByText("+22.5% (7d)")).toBeVisible();
		await expect(page.getByText("-3.2% (7d)")).toBeVisible();
	});

	test("HD-2: renders quota progress bars with warning and alert thresholds", async ({ page }) => {
		await page.goto("/dashboard/1/health");

		// Quota card
		await expect(page.getByText("Quota Utilization & Plan Progression")).toBeVisible();

		// Utilization items
		await expect(page.getByText("Memory Capacity")).toBeVisible();
		await expect(page.getByText("Warning (80%+)")).toBeVisible(); // 85% utilization warning badge
		await expect(page.getByText("Recommended tier: Team")).toBeVisible(); // Recommended tier CTA

		await expect(page.getByText("Monthly Credits")).toBeVisible();
		await expect(page.getByText("Quota Exceeded")).toBeVisible(); // 105% alert badge

		await expect(page.getByText("Storage Allocation")).toBeVisible();
	});

	test("HD-3 & HD-5: displays top sources ranked table and opens drilldown sheet", async ({
		page,
	}) => {
		await page.goto("/dashboard/1/health");

		// Table heading
		await expect(page.getByText("Knowledge & Scraper Sources")).toBeVisible();

		// Table rows
		await expect(page.getByRole("cell", { name: "document" })).toBeVisible();
		await expect(page.getByRole("cell", { name: "slack connector" })).toBeVisible();

		// Click source row to open HD-5 drilldown sheet
		await page.getByRole("cell", { name: "document" }).first().click();

		// Sheet header
		await expect(page.getByText("document Drilldown")).toBeVisible();
		await expect(
			page.getByText("Ingestion history, query citations, and timeline samples")
		).toBeVisible();

		// Timeline samples inside sheet
		await expect(page.getByText("Quarterly product roadmap meeting minutes")).toBeVisible();
		await expect(page.getByText("Engineering sprint retrospective notes")).toBeVisible();
	});

	test("HD-4: detects coverage gaps and opens slide-over drawer", async ({ page }) => {
		await page.goto("/dashboard/1/health");

		// Coverage gap banner alert
		const gapTrigger = page.getByRole("button", { name: /coverage gaps/i });
		await expect(gapTrigger).toBeVisible();
		await gapTrigger.click();

		// Drawer heading
		await expect(page.getByRole("heading", { name: "Knowledge Coverage Gaps" })).toBeVisible();
		await expect(
			page.getByRole("dialog", { name: "Knowledge Coverage Gaps" }).getByText("google drive")
		).toBeVisible();
		await expect(
			page.getByText("Trigger manual sync or verify connector credentials")
		).toBeVisible();
		await expect(page.getByRole("link", { name: /configure/i })).toBeVisible();
	});

	test("Time Range toggle switches date range filter", async ({ page }) => {
		let requestedRange = "";
		await page.route("**/api/v1/workspaces/1/health?**", async (route) => {
			const url = new URL(route.request().url());
			requestedRange = url.searchParams.get("range") || "";
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({ ...mockSummaryFull, date_range: requestedRange }),
			});
		});

		await page.goto("/dashboard/1/health");

		// Click 7d button
		await page.getByRole("button", { name: "7D" }).click();
		expect(requestedRange).toBe("7d");

		// Click 90d button
		await page.getByRole("button", { name: "90D" }).click();
		expect(requestedRange).toBe("90d");
	});

	test("INV-29.3: renders public snapshot notice and masks protected metrics", async ({ page }) => {
		const mockPublicSnapshot = {
			...mockSummaryFull,
			is_public_snapshot: true,
			active_members_dau: null,
			active_members_wau: null,
			credits_consumed_micros: null,
			cost_per_turn_micros: null,
			quota_progress: null,
		};

		await page.route("**/api/v1/workspaces/1/health?**", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(mockPublicSnapshot),
			});
		});

		await page.goto("/dashboard/1/health");

		// Public snapshot notice banner
		await expect(page.getByText("Public Snapshot Mode:")).toBeVisible();
		await expect(page.getByText("INV-29.3 Read Only")).toBeVisible();

		// Financial and member metric masking assertions
		const protectedBadges = page.getByText("Protected");
		expect(await protectedBadges.count()).toBeGreaterThanOrEqual(3);
	});

	test("renders empty state onboarding guidance when no activity exists", async ({ page }) => {
		const mockEmpty = {
			...mockSummaryFull,
			total_memories: { current_value: 0, change_pct: null, sparkline: [] },
			query_volume: { current_value: 0, change_pct: null, sparkline: [] },
			top_sources: [],
			quota_progress: [],
		};

		await page.route("**/api/v1/workspaces/1/health?**", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify(mockEmpty),
			});
		});

		await page.goto("/dashboard/1/health");

		// Empty state guidance
		await expect(page.getByText("No Health Activity Yet")).toBeVisible();
		await expect(page.getByText("Start by connecting your workspace data sources")).toBeVisible();
		await expect(page.getByRole("link", { name: /connect sources/i })).toBeVisible();
	});
});
