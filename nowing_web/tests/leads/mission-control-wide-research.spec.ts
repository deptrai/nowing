import { expect, test } from "../fixtures";

test.describe("Mission Control — research_mode=wide (26.9a)", () => {
	test("should not crash when a wide-research mission includes a wide_research_matrix", async ({
		page,
		workspace,
	}) => {
		const listPattern = new RegExp(`/api/v1/workspaces/${workspace.id}/dsh/missions(?:\\?.*)?$`);
		const controlPattern = new RegExp(
			`/api/v1/workspaces/${workspace.id}/dsh/missions/[\\w-]+/control$`
		);

		const missionId = "00000000-0000-0000-0000-000000000002";

		// Mock the mission list to return a single running wide-research mission.
		await page.route(listPattern, async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					items: [
						{
							id: missionId,
							workspace_id: workspace.id,
							mission_type: "deep_lead_research",
							status: "running",
							phase: "reasoning",
							progress_percent: 45,
							current_subtask_id: "crawl",
							created_at: new Date().toISOString(),
							updated_at: new Date().toISOString(),
						},
					],
					total: 1,
					limit: 50,
					offset: 0,
				}),
			});
		});

		// Mock the control response to include a wide_research_matrix and a crawl subtask.
		// The frontend should ignore fields it does not yet display and not crash.
		await page.route(controlPattern, async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					id: missionId,
					workspace_id: workspace.id,
					mission_type: "deep_lead_research",
					status: "running",
					phase: "reasoning",
					progress_percent: 45,
					current_subtask_id: "crawl",
					created_at: new Date().toISOString(),
					updated_at: new Date().toISOString(),
					token_velocity: {
						tokens_total: 0,
						tokens_per_second: 0,
						cost_micros: 12000,
						cost_credits: 0.012,
					},
					subtasks: [
						{
							id: "crawl",
							title: "Crawl",
							status: "success",
							phase: "crawl",
							reasoning_content: "",
							tokens_used: 0,
							tokens_per_second: 0,
							run_id: "run_26-9a-wide",
							cost_micros: 12000,
							started_at: new Date().toISOString(),
							completed_at: new Date().toISOString(),
							sources_count: 2,
						},
						{
							id: "reasoning",
							title: "Reasoning",
							status: "running",
							phase: "reasoning",
							reasoning_content: "",
							tokens_used: 0,
							tokens_per_second: 0,
							run_id: null,
							cost_micros: 0,
							started_at: new Date().toISOString(),
							completed_at: null,
						},
					],
					// New 26.9a fields that the backend may include in the future.
					// The frontend must not crash on them.
					wide_research_matrix: {
						topics: ["framework", "model"],
						sources: [
							{ title: "LangChain", url: "https://langchain.com", source_type: "web" },
							{ title: "LangGraph", url: "https://langgraph.com", source_type: "web" },
						],
						matrix: [
							[true, false],
							[false, true],
						],
					},
					degraded: false,
					degradation_reason: null,
				}),
			});
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);

		// The mission control widget appears.
		await expect(page.getByTestId("mission-control-widget")).toBeVisible({
			timeout: 10000,
		});

		// The stepper shows the crawl and reasoning stages.
		await expect(page.getByTestId("mission-control-stepper")).toContainText("Crawl");
		await expect(page.getByTestId("mission-control-stepper")).toContainText("Reasoning");

		// No Next.js error overlay.
		await expect(page.getByText(/Application error/i)).toHaveCount(0);
	});
});
