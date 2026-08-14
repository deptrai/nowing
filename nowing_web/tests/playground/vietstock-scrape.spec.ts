import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * End-to-end smoke tests for the Vietstock capability in the API Playground.
 *
 * These tests exercise the real frontend + backend stack. They verify:
 *   1. The capability is listed in the playground catalog.
 *   2. The runner page loads without a Next.js crash / white-screen.
 *   3. A degraded response is surfaced without crashing.
 *   4. A successful quote + financials response renders new fields without crashing.
 */

test.describe("Playground Vietstock scrape", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ page, request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E Vietstock ${Date.now()}`);
		workspaceId = workspace.id;

		await page.route(
			/.*\/api\/v1\/workspaces\/\d+\/scrapers\/vietstock\/scrape(\?.*)?$/,
			async (route) => {
				const req = route.request();
				if (req.method() === "OPTIONS") {
					await route.fulfill({ status: 204 });
					return;
				}

				if (req.method() === "POST") {
					await route.fulfill({
						status: 200,
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({
							quote: null,
							financials: null,
							cost_micros: 0,
							degraded: true,
							degradation_reason: "api_error",
							total_items: 0,
						}),
					});
					return;
				}

				await route.continue();
			}
		);
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("should render Vietstock scrape in the playground catalog", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground`);

		const link = page.getByRole("link", { name: /vietstock/i });
		await expect(link).toBeVisible();
		await expect(link).toContainText("vietstock.scrape");

		await link.click();
		await expect(page).toHaveURL(`/dashboard/${workspaceId}/playground/vietstock/scrape`);
	});

	test("should load the runner page without a white-screen crash", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/vietstock/scrape`);

		await expect(page.getByRole("heading", { name: "API Playground" })).toBeVisible();
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});

	test("should surface a degraded result without crashing", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/vietstock/scrape`);

		const symbolInput = page.locator("#field-symbol");
		await expect(symbolInput).toBeVisible();
		await symbolInput.fill("VNM");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		await expect(page.getByText(/degraded|api_error|api error/i).first()).toBeVisible({
			timeout: 30_000,
		});
	});

	test("should render a successful result with quote and financials", async ({ page }) => {
		await page.unroute(/.*\/api\/v1\/workspaces\/\d+\/scrapers\/vietstock\/scrape(\?.*)?$/);

		await page.route(
			/.*\/api\/v1\/workspaces\/\d+\/scrapers\/vietstock\/scrape(\?.*)?$/,
			async (route) => {
				const req = route.request();
				if (req.method() === "OPTIONS") {
					await route.fulfill({ status: 204 });
					return;
				}
				if (req.method() === "POST") {
					await route.fulfill({
						status: 200,
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({
							quote: {
								symbol: "VNM",
								current_price: 61.6,
								change: 0,
								change_percent: 0,
								key_ratios: { pe: 11.74, pb: 3.61 },
							},
							financials: {
								symbol: "VNM",
								balance_sheet: {
									periods: ["Q3-2025", "Q4-2025", "Q1-2026", "Q2-2026"],
									items: [
										{
											code: "2996",
											name: "Tổng tài sản",
											values: [
												57_451_803_693_875, 55_429_011_127_169, 53_312_370_717_301,
												55_677_822_006_663,
											],
										},
									],
									key_metrics: {
										tong_tai_san: [
											57_451_803_693_875, 55_429_011_127_169, 53_312_370_717_301,
											55_677_822_006_663,
										],
									},
									unit: "VND",
								},
								income_statement: {
									periods: ["Q3-2025", "Q4-2025", "Q1-2026", "Q2-2026"],
									items: [
										{
											code: "2216",
											name: "Doanh thu thuần",
											values: [
												18_847_347_464_988, 16_148_657_871_623, 17_033_552_405_954,
												16_953_231_537_863,
											],
										},
									],
									key_metrics: {
										doanh_thu_thuan: [
											18_847_347_464_988, 16_148_657_871_623, 17_033_552_405_954,
											16_953_231_537_863,
										],
									},
									unit: "VND",
								},
								cash_flow: {
									periods: [],
									items: [],
									key_metrics: {},
									unit: "VND",
								},
							},
							cost_micros: 5000,
							degraded: false,
							degradation_reason: null,
							total_items: 1,
						}),
					});
					return;
				}
				await route.continue();
			}
		);

		await page.goto(`/dashboard/${workspaceId}/playground/vietstock/scrape`);

		const symbolInput = page.locator("#field-symbol");
		await symbolInput.fill("VNM");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		await expect(page.getByText(/VNM|61\.6|Tổng tài sản|Doanh thu thuần/i).first()).toBeVisible({
			timeout: 30_000,
		});
	});
});
