import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * End-to-end smoke tests for the TopCV capability in the API Playground.
 */

test.describe("Playground TopCV scrape", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ page, request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E TopCV ${Date.now()}`);
		workspaceId = workspace.id;

		await page.route(
			/.*\/api\/v1\/workspaces\/\d+\/scrapers\/topcv\/scrape(\?.*)?$/,
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
								id: "topcv:1599438",
								title: "ETL Developer - Data Engineer",
								company: "Công Ty TNHH LG CNS VIỆT NAM",
								location: "Hà Nội",
								salary_raw: "Thoả thuận",
								salary_min: 0,
								salary_max: 0,
								salary_currency: "VND",
								salary_period_id: "negotiable",
								employment_type: "full_time",
								experience_years: 3,
								job_description: "Develop in web application",
								job_requirement: "Bachelor's degree",
								skills: ["Data Engineer", "SQL"],
								posted_at: "2026-08-06T00:00:00+00:00",
								is_active: true,
								source: "topcv",
							},
						],
						cost_micros: 5500,
						degraded: false,
						degradation_reason: null,
						total_items: 1,
					}),
				});
			}
		);
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("should render TopCV scrape in the playground catalog", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground`);

		const link = page.getByRole("link", { name: /topcv/i });
		await expect(link).toBeVisible();
		await expect(link).toContainText("topcv.scrape");

		await link.click();
		await expect(page).toHaveURL(`/dashboard/${workspaceId}/playground/topcv/scrape`);
	});

	test("should load the runner page without a white-screen crash", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/topcv/scrape`);

		await expect(page.getByRole("heading", { name: "API Playground" })).toBeVisible();
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});

	test("should surface a scrape result without crashing", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/topcv/scrape`);

		const keywordInput = page.locator("#field-keyword");
		await keywordInput.fill("data engineer");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		await expect(page.getByText(/ETL Developer|Công Ty|topcv/i).first()).toBeVisible();
	});
});
