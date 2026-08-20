import { expect, test } from "../fixtures";
import { acquireTestToken } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

const WIDE_MATRIX = {
	topics: ["framework", "model"],
	sources: [
		{ title: "LangChain Docs", url: "https://langchain.com", source_type: "web" },
		{ title: "LangGraph Docs", url: "https://langgraph.com", source_type: "web" },
	],
	matrix: [
		[true, false],
		[false, true],
	],
};

const RESEARCH_OUTPUT = {
	answer: "",
	sources: [],
	structured_output: WIDE_MATRIX,
	cost_micros: 12000,
	billable_units: 1,
	degraded: false,
	status: "complete",
};

const RUN_ID = "run_00000000-0000-0000-0000-000000000001";

test.describe("Research wide table output — 26.9a", () => {
	let token: string;
	let workspace: { id: number; name: string };

	test.beforeEach(async ({ request }) => {
		token = await acquireTestToken(request);
		workspace = await createWorkspace(request, token, `E2E Research Wide ${Date.now()}`);
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, token, workspace.id);
	});

	test("should render chainlens.research run with structured_output in playground without crashing", async ({
		page,
	}) => {
		// Mock the runs list so the playground shows a wide-research run.
		await page.route(
			new RegExp(`/api/v1/workspaces/${workspace.id}/scrapers/runs(?:\\?.*)?$`),
			async (route) => {
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify([
						{
							id: RUN_ID,
							capability: "chainlens.research",
							origin: "ui",
							status: "success",
							item_count: 2,
							char_count: 0,
							duration_ms: 4500,
							cost_micros: 12000,
							error: null,
							created_at: new Date().toISOString(),
						},
					]),
				});
			}
		);

		// Mock the run detail to return a wide-research result with structured_output.
		await page.route(
			new RegExp(`/api/v1/workspaces/${workspace.id}/scrapers/runs/${RUN_ID}$`),
			async (route) => {
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({
						id: RUN_ID,
						capability: "chainlens.research",
						origin: "ui",
						status: "success",
						item_count: 2,
						char_count: 0,
						duration_ms: 4500,
						cost_micros: 12000,
						error: null,
						created_at: new Date().toISOString(),
						thread_id: null,
						input: {
							query: "so sánh 20 framework AI Agent 2026",
							output: "table",
						},
						output_text: JSON.stringify(RESEARCH_OUTPUT),
						progress: null,
					}),
				});
			}
		);

		await page.goto(`/dashboard/${workspace.id}/playground/runs`);

		// The run row appears.
		await expect(page.getByText("chainlens.research").first()).toBeVisible();

		// Expand the run row.
		await page.getByText("chainlens.research").first().click();

		// The output panel and JSON tab render.
		await expect(page.getByRole("heading", { name: /Output/i })).toBeVisible();
		await page.getByRole("tab", { name: "JSON" }).click();

		// The wide-research matrix fields are visible.
		await expect(page.getByText(/"structured_output"/i).first()).toBeVisible();
		await expect(page.getByText(/"topics"/i).first()).toBeVisible();
		await expect(page.getByText(/"matrix"/i).first()).toBeVisible();

		// No Next.js error overlay.
		await expect(page.getByText(/Application error/i)).toHaveCount(0);
	});
});
