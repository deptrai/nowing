import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * End-to-end smoke tests for the ITviec capability in the API Playground.
 */

test.describe("Playground ITviec scrape", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ page, request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E ITviec ${Date.now()}`);
		workspaceId = workspace.id;

		await page.route(
			/.*\/api\/v1\/workspaces\/\d+\/scrapers\/itviec\/scrape(\?.*)?$/,
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
								id: "itviec:data-engineer-global-e-commerce-data-platform-crossian-2727",
								title: "Data Engineer, Global E-commerce Data Platform",
								company: "Crossian",
								location: "Ha Noi",
								salary_raw: "Sign in to view salary",
								salary_min: 0,
								salary_max: 0,
								salary_currency: "VND",
								salary_period_id: "hidden",
								employment_type: "full_time",
								experience_years: null,
								job_description: "ABOUT THE ROLE",
								job_requirement: "Bachelor's degree",
								skills: ["Data Engineer", "AWS", "Python"],
								posted_at: "2026-08-05",
								is_active: true,
								source: "itviec",
							},
						],
						cost_micros: 3000,
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

	test("should render ITviec scrape in the playground catalog", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground`);

		const link = page.getByRole("link", { name: /itviec/i });
		await expect(link).toBeVisible();
		await expect(link).toContainText("itviec.scrape");

		await link.click();
		await expect(page).toHaveURL(`/dashboard/${workspaceId}/playground/itviec/scrape`);
	});

	test("should load the runner page without a white-screen crash", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/itviec/scrape`);

		await expect(page.getByRole("heading", { name: "API Playground" })).toBeVisible();
		await expect(page.getByText(/application error/i)).toHaveCount(0);
	});

	test("should surface a scrape result without crashing", async ({ page }) => {
		await page.goto(`/dashboard/${workspaceId}/playground/itviec/scrape`);

		const keywordInput = page.locator("#field-keyword");
		await keywordInput.fill("data engineer");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		await expect(page.getByText(/Data Engineer|Crossian|itviec/i).first()).toBeVisible();
	});
});
