import type { Page, Route } from "@playwright/test";
import { expect, test } from "../fixtures";
import { fulfillJson } from "../helpers/cors";
import { mockAdminAuth } from "../helpers/admin-auth";

/**
 * Story 25.5: Dynamic Scraper Rule Engine & ReDoS Sandbox.
 *
 * Red-phase E2E scaffolds for `/admin/scrapers/rules`. Tests are skipped until
 * the backend routes and frontend page are implemented. They exercise the admin
 * dashboard by intercepting the backend API and serving deterministic responses.
 */

const mockRulesList = {
	items: [
		{
			platform: "batdongsan",
			version: 7,
			is_active: true,
			updated_at: "2026-08-26T10:00:00Z",
			updated_by: "Super Admin",
			circuit_breaker_tripped: false,
		},
		{
			platform: "chotot",
			version: 3,
			is_active: false,
			updated_at: "2026-08-26T09:00:00Z",
			updated_by: "Super Admin",
			circuit_breaker_tripped: false,
		},
	],
	total: 2,
};

const mockActiveRule = {
	platform: "batdongsan",
	version: 7,
	is_active: true,
	updated_at: "2026-08-26T10:00:00Z",
	updated_by: "Super Admin",
	rule_schema: {
		selectors: {
			listing_card: "div.js__card-listing",
			title: "span.js__card-title",
			price: "span.re__card-config-price",
			next_page_link: "a.next",
		},
		regexes: {
			phone_in_title: "(?:^|[^\\d])(?:\\+84|84|0)[0-9\\s.\\-]{8,15}(?:[^\\d]|$)",
		},
		delays: {
			request_ms: 1500,
			retry_base_ms: 1000,
		},
		retries: {
			max_attempts: 3,
			statuses: [429, 500, 502, 503],
		},
		circuit_breaker: {
			error_threshold_pct: 20,
			min_calls: 10,
			trip_duration_seconds: 300,
			tripped: false,
		},
	},
};

const mockValidationError = {
	detail: [
		{
			loc: ["rule_schema", "selectors", "title"],
			msg: "Invalid CSS selector: span[",
			type: "value_error.invalid_css",
		},
	],
};

const mockRedosError = {
	code: "REDOS_TIMEOUT",
	detail: "REDOS_TIMEOUT: Regex exceeds 50ms ReDoS limit",
};


async function setupApiMocks(page: Page) {
	await mockAdminAuth(page);

	await page.route("**/api/v1/admin/scraper-rules", async (route: Route) => {
		await fulfillJson(route, 200, mockRulesList);
	});

	await page.route("**/api/v1/admin/scraper-rules/batdongsan", async (route: Route) => {
		await fulfillJson(route, 200, mockActiveRule);
	});
}

test.describe("Admin Scraper Rules page", () => {
	test.beforeEach(async ({ page }) => {
		await setupApiMocks(page);
	});

	test("renders the rules list and active rule details", async ({ page }) => {
		await page.goto("/admin/scrapers/rules");
		await expect(page.getByText("batdongsan").first()).toBeVisible();
		await expect(page.getByText("version 7").first()).toBeVisible();
		await expect(page.locator("[data-testid='rule-editor-selectors-title']")).toHaveValue(
			"span.js__card-title"
		);
	});

	test("validates invalid CSS selector inline", async ({ page }) => {
		await page.route("**/api/v1/admin/scraper-rules/batdongsan", async (route: Route) => {
			if (route.request().method() === "POST") {
				await fulfillJson(route, 422, mockValidationError);
			} else {
				await fulfillJson(route, 200, mockActiveRule);
			}
		});
		await page.goto("/admin/scrapers/rules");
		await expect(page.locator("[data-testid='rule-editor-selectors-title']")).toHaveValue(
			"span.js__card-title"
		);
		await page.fill("[data-testid='rule-editor-selectors-title']", "span[");
		await page.click("text=Save");
		await expect(page.getByText(/Invalid CSS selector/i)).toBeVisible();
	});

	test("validates ReDoS regex inline", async ({ page }) => {
		await page.route("**/api/v1/admin/scraper-rules/batdongsan", async (route: Route) => {
			if (route.request().method() === "POST") {
				await fulfillJson(route, 422, mockRedosError);
			} else {
				await fulfillJson(route, 200, mockActiveRule);
			}
		});
		await page.goto("/admin/scrapers/rules");
		await expect(page.locator("[data-testid='rule-editor-regexes-phone_in_title']")).toBeVisible();
		await page.fill("[data-testid='rule-editor-regexes-phone_in_title']", "(a+)+$");
		await page.click("text=Save");
		await expect(page.getByText(/REDOS_TIMEOUT/i)).toBeVisible();
	});

	test("trip circuit breaker updates status", async ({ page }) => {
		await page.goto("/admin/scrapers/rules");
		await page.route(
			"**/api/v1/admin/scraper-rules/batdongsan/circuit-breaker/trip",
			async (route: Route) => {
				await fulfillJson(route, 200, {
					...mockActiveRule,
					rule_schema: {
						...mockActiveRule.rule_schema,
						circuit_breaker: { ...mockActiveRule.rule_schema.circuit_breaker, tripped: true },
					},
				});
			}
		);
		await page.click("text=Trip Circuit Breaker");
		await expect(page.getByText("status: tripped")).toBeVisible();
	});

	test("reset circuit breaker updates status", async ({ page }) => {
		await page.goto("/admin/scrapers/rules");
		await page.route(
			"**/api/v1/admin/scraper-rules/batdongsan/circuit-breaker/reset",
			async (route: Route) => {
				await fulfillJson(route, 200, {
					...mockActiveRule,
					rule_schema: {
						...mockActiveRule.rule_schema,
						circuit_breaker: { ...mockActiveRule.rule_schema.circuit_breaker, tripped: false },
					},
				});
			}
		);
		await page.click("text=Reset Circuit Breaker");
		await expect(page.getByText("status: healthy")).toBeVisible();
	});

	test("polls the list every 5 seconds", async ({ page }) => {
		let callCount = 0;
		await page.route("**/api/v1/admin/scraper-rules", async (route: Route) => {
			callCount += 1;
			await fulfillJson(route, 200, { ...mockRulesList, total: callCount });
		});
		await page.goto("/admin/scrapers/rules");
		await page.waitForTimeout(5500);
		await expect.poll(() => callCount).toBeGreaterThanOrEqual(2);
	});
});
