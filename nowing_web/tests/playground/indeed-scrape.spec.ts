import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";
import { mockScraperRun } from "../helpers/mock-scraper-run";

/**
 * End-to-end smoke tests for the Indeed capability in the API Playground.
 *
 * These tests exercise the real frontend + backend stack. They verify:
 *   1. The capability is listed in the playground catalog.
 *   2. The runner page loads without a Next.js crash / white-screen.
 *   3. A successful scrape response renders job fields without crashing.
 *   4. A degraded response (anti_bot_block) is surfaced without crashing.
 *   5. An empty-results response (0 items, not degraded) doesn't crash.
 *   6. Auth session expiry redirects to /login without a redirect loop.
 *   7. A quota-exceeded 402 error envelope is surfaced via error toast.
 */

const successPayload = {
	items: [
		{
			id: "indeed:91817aa16b89d707",
			title: "Data Engineer",
			company: "Freudenberg-NOK General Partnership",
			location: "Hybrid work in Plymouth, MI",
			salary_raw: "$120,000 a year",
			salary_min: 120000,
			salary_max: 120000,
			salary_currency: "USD",
			salary_period_id: "year",
			employment_type: "full_time",
			experience_years: null,
			job_description: "Build scalable lakehouse pipelines on Azure Databricks",
			job_requirement: "Degree in Computer Science or related field",
			benefits: ["Health insurance", "401(k) matching"],
			skills: [],
			posted_at: "2026-08-05T00:00:00+00:00",
			is_active: true,
			source: "indeed",
		},
	],
	cost_micros: 5000,
	degraded: false,
	degradation_reason: null,
	total_items: 1,
};

const degradedPayload = {
	items: [],
	cost_micros: 0,
	degraded: true,
	degradation_reason: "anti_bot_block",
	total_items: 0,
};

const emptyPayload = {
	items: [],
	cost_micros: 0,
	degraded: false,
	degradation_reason: null,
	total_items: 0,
};

test.describe("Playground Indeed scrape", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E Indeed ${Date.now()}`);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("should render Indeed scrape in the playground catalog", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground`);

		const link = page.getByRole("link", { name: /indeed/i });
		await expect(link).toBeVisible();
		await expect(link).toContainText("indeed.scrape");

		await link.click();
		await expect(page).toHaveURL(`/dashboard/${workspaceId}/playground/indeed/scrape`);
	});

	test("should load the runner page without a white-screen crash", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/indeed/scrape`);

		await expect(page.getByRole("heading", { name: "API Playground" })).toBeVisible();
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});

	test("should surface a scrape result without crashing", async ({ page }) => {
		await mockScraperRun(page, {
			platform: "indeed",
			verb: "scrape",
			payload: successPayload,
			input: { keyword: "data engineer" },
		});

		await page.goto(`/dashboard/${workspaceId}/playground/indeed/scrape`);

		const advanced = page.getByRole("button", { name: /advanced/i });
		await advanced.click();

		const keywordInput = page.locator("#field-keyword");
		await keywordInput.fill("data engineer");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		const jsonTab = page.getByRole("tab", { name: /^json$/i });
		await expect(jsonTab).toBeVisible({ timeout: 30_000 });
		await jsonTab.click();
		await expect(
			page
				.locator("pre:visible")
				.getByText(/Data Engineer|Freudenberg/i)
				.first()
		).toBeVisible({ timeout: 15_000 });
	});

	test("should surface a degraded (anti_bot_block) response without crashing", async ({ page }) => {
		await mockScraperRun(page, {
			platform: "indeed",
			verb: "scrape",
			payload: degradedPayload,
			input: { keyword: "data engineer" },
			itemCount: 0,
		});

		await page.goto(`/dashboard/${workspaceId}/playground/indeed/scrape`);

		const advanced = page.getByRole("button", { name: /advanced/i });
		await advanced.click();

		const keywordInput = page.locator("#field-keyword");
		await keywordInput.fill("data engineer");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		const jsonTab = page.getByRole("tab", { name: /^json$/i });
		await expect(jsonTab).toBeVisible({ timeout: 30_000 });
		await jsonTab.click();
		await expect(
			page
				.locator("pre:visible")
				.getByText(/degraded|anti_bot|blocked/i)
				.first()
		).toBeVisible({ timeout: 15_000 });
	});

	test("should handle an empty-results response (0 items, not degraded) without crashing", async ({
		page,
	}) => {
		await mockScraperRun(page, {
			platform: "indeed",
			verb: "scrape",
			payload: emptyPayload,
			input: { keyword: "zzz nonexistent job title 999" },
			itemCount: 0,
		});

		await page.goto(`/dashboard/${workspaceId}/playground/indeed/scrape`);

		const advanced = page.getByRole("button", { name: /advanced/i });
		await advanced.click();

		const keywordInput = page.locator("#field-keyword");
		await keywordInput.fill("zzz nonexistent job title 999");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		// The runner should not crash — the run detail renders (empty items).
		const jsonTab = page.getByRole("tab", { name: /^json$/i });
		await expect(jsonTab).toBeVisible({ timeout: 30_000 });
		await jsonTab.click();
		await expect(
			page
				.locator("pre:visible")
				.getByText(/items|total_items/i)
				.first()
		).toBeVisible({ timeout: 15_000 });
	});

	test("should redirect to /login on session expiry without a redirect loop", async ({
		page,
		context,
	}) => {
		await page.goto(`/dashboard/${workspaceId}/playground/indeed/scrape`);

		// Wait for the page to be fully loaded before clearing cookies.
		await expect(page.getByRole("heading", { name: "API Playground" })).toBeVisible();

		// Force session expiry by clearing the session cookie mid-flow.
		await context.clearCookies();
		await page.reload();

		await expect(page).toHaveURL(/\/login/, { timeout: 30_000 });
		await expect(page.getByRole("heading", { name: /log in|sign in/i })).toBeVisible();
	});

	test("should surface a quota-exceeded 402 error without crashing", async ({ page }) => {
		// The async run start (POST ?mode=async) returns a 402 error envelope.
		await page.route(/.*\/api\/v1\/workspaces\/\d+\/scrapers\/indeed\/scrape/, async (route) => {
			const req = route.request();
			if (req.method() === "OPTIONS") {
				await route.fulfill({ status: 204 });
				return;
			}
			if (req.method() === "POST") {
				await route.fulfill({
					status: 402,
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						error: {
							code: "INSUFFICIENT_CREDITS",
							message: "Insufficient credits to complete this scrape.",
							status: 402,
							request_id: "e2e-test-req-id",
							timestamp: new Date().toISOString(),
						},
						detail: "Workspace has insufficient credits for indeed.scrape.",
					}),
				});
				return;
			}
			await route.continue();
		});

		await page.goto(`/dashboard/${workspaceId}/playground/indeed/scrape`);

		const advanced = page.getByRole("button", { name: /advanced/i });
		await advanced.click();

		const keywordInput = page.locator("#field-keyword");
		await keywordInput.fill("data engineer");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		// The error toast or inline error should surface the quota message.
		await expect(page.getByText(/credit|quota|insufficient/i).first()).toBeVisible({
			timeout: 30_000,
		});
	});
});
