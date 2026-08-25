import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * End-to-end smoke tests for the Vietnam Job Market aggregator in the API Playground.
 *
 * These tests exercise the real frontend + backend stack. They verify:
 *   1. The aggregator is listed in the playground catalog.
 *   2. The runner page loads without a Next.js crash / white-screen.
 *   3. A multi-source aggregate run surfaces results and handles degraded sources.
 */

test.describe("Playground VN Jobs aggregate", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ page, request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E VN Jobs ${Date.now()}`);
		workspaceId = workspace.id;

		// Block the aggregator run endpoint so tests never trigger a real
		// live call to VietnamWorks/TopCV/ITviec.
		await page.route(
			/.*\/api\/v1\/workspaces\/\d+\/scrapers\/vn_jobs\/aggregate(\?.*)?$/,
			async (route) => {
				const req = route.request();
				if (req.method() === "OPTIONS") {
					await route.fulfill({ status: 204 });
					return;
				}
				await route.fulfill({
					status: 200,
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						items: [
							{
								id: "vw:1",
								title: "Senior Data Engineer",
								company: "ACB",
								location: "Hà Nội",
								employment_type: "full_time",
								experience_years: 3,
								skills: ["Python", "SQL"],
								salary: {
									min: 30000000,
									max: 50000000,
									currency: "VND",
									period: "month",
									raw: "30-50 triệu",
								},
								posted_at: "2026-08-05",
								job_description: "Build data pipelines",
								job_requirement: "3 years exp",
								source: "vietnamworks",
								source_urls: ["https://www.vietnamworks.com/senior-data-engineer-1-jv"],
								confidence_score: 0.6,
								salary_consistency_score: 0.9,
								conflict: false,
								pii_redacted: false,
							},
						],
						cost_micros: 9000,
						degraded: true,
						degradation_reasons: ["topcv: anti_bot_poc_pending", "itviec: tos_review_pending"],
						source_breakdown: {
							vietnamworks: { total: 1, degraded: false },
							topcv: { total: 0, degraded: true, degradation_reason: "anti_bot_poc_pending" },
							itviec: { total: 0, degraded: true, degradation_reason: "tos_review_pending" },
						},
						total_items: 1,
					}),
				});
			}
		);
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("should render vn_jobs.aggregate in the playground catalog", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground`);

		const link = page.getByRole("link", { name: /vn_jobs/i });
		await expect(link).toBeVisible();
		await expect(link).toContainText("vn_jobs.aggregate");

		await link.click();
		await expect(page).toHaveURL(`/dashboard/${workspaceId}/playground/vn_jobs/aggregate`);
	});

	test("should load the aggregator runner page without a white-screen crash", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/vn_jobs/aggregate`);

		await expect(page.getByRole("heading", { name: "API Playground" })).toBeVisible();
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});

	test("should surface an aggregate result without crashing", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/vn_jobs/aggregate`);

		const keywordInput = page.locator("#field-keyword");
		await keywordInput.fill("data engineer");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		await expect(page.getByText(/Senior Data Engineer|degraded|topcv/i).first()).toBeVisible();
	});
});
