import { expect, test } from "@playwright/test";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

/**
 * End-to-end smoke tests for the Indeed capability in the API Playground.
 */

test.describe("Playground Indeed scrape", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ page, request }) => {
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E Indeed ${Date.now()}`);
		workspaceId = workspace.id;

		await page.route(
			/.*\/api\/v1\/workspaces\/\d+\/scrapers\/indeed\/scrape(\?.*)?$/,
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
								skills: ["Databricks", "PySpark", "SQL"],
								posted_at: "2026-08-05T00:00:00+00:00",
								is_active: true,
								source: "indeed",
							},
						],
						cost_micros: 8000,
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
		await page.goto(`/dashboard/${workspaceId}/playground/indeed/scrape`);

		// Expand the advanced inputs if they are collapsed.
		const advanced = page.getByRole("button", { name: /advanced/i });
		await advanced.click();

		const keywordInput = page.locator("#field-keyword");
		await keywordInput.fill("data engineer");

		const runButton = page.getByRole("button", { name: /run/i });
		await runButton.click();

		await expect(page.getByText(/application error/i)).toHaveCount(0);
		await expect(page.getByText(/Data Engineer|Freudenberg|indeed/i).first()).toBeVisible();
	});
});
