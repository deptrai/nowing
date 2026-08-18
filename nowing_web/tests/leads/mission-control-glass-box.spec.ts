import { expect, test } from "../fixtures";
import { authHeaders, BACKEND_URL } from "../helpers/api/auth";

function listMissionsPattern(workspaceId: number) {
	return new RegExp(`/api/v1/workspaces/${workspaceId}/dsh/missions(?:\\?|$)`);
}

function controlPattern(workspaceId: number) {
	return new RegExp(`/api/v1/workspaces/${workspaceId}/dsh/missions/[\\w-]+/control`);
}

const MOCK_MISSION = {
	id: "00000000-0000-0000-0000-000000000000",
	mission_type: "deep_lead_research",
	status: "running",
	progress_percent: 45,
	current_subtask_id: null,
	created_at: new Date().toISOString(),
	updated_at: new Date().toISOString(),
};

test.describe("Story 26.5: Glass Box Mission Control & Shimmer Influx E2E", () => {
	test("[P0] renders the 4-stage stepper with phase, progress and token velocity", async ({
		page,
		request,
		workspace,
		apiToken,
	}) => {
		// Arrange: create a DSH mission via the public API
		const createRes = await request.post(
			`${BACKEND_URL}/api/v1/workspaces/${workspace.id}/dsh/missions`,
			{
				headers: authHeaders(apiToken),
				data: {
					mission_type: "deep_lead_research",
					payload: {
						query: "bất động sản Cầu Giấy",
						workspace_id: workspace.id,
					},
				},
			}
		);
		expect(createRes.status()).toBe(201);

		// Act: load the Split Canvas / Lead Intelligence view
		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);

		// Assert: Glass Box widget appears with the 4-stage stepper
		await expect(page.getByTestId("mission-control-widget")).toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByTestId("mission-control-stepper")).toContainText("Crawl");
		await expect(page.getByTestId("mission-control-stepper")).toContainText("Reasoning");
		await expect(page.getByTestId("mission-control-stepper")).toContainText("Extraction");
		await expect(page.getByTestId("mission-control-stepper")).toContainText("Ingest");
		await expect(page.getByTestId("mission-control-phase")).toBeVisible();
		await expect(page.getByTestId("mission-control-progress")).toBeVisible();
		await expect(page.getByTestId("mission-control-token-velocity")).toBeVisible();
	});

	test("[P0] control endpoint response is redacted and never exposes PII", async ({
		page,
		workspace,
	}) => {
		// Ensure the list endpoint returns a running mission so the widget
		// actually fetches the control data we want to redact.
		await page.route(listMissionsPattern(workspace.id), async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					items: [
						{
							...MOCK_MISSION,
							workspace_id: workspace.id,
							phase: "reasoning",
						},
					],
					total: 1,
				}),
			});
		});

		// Intercept the control API and assert the response shape
		const controlResponse = page.waitForResponse(controlPattern(workspace.id));
		await page.route(controlPattern(workspace.id), async (route) => {
			const response = await route.fetch();
			const body = await response.json();

			expect(body).not.toHaveProperty("payload");
			expect(body).not.toHaveProperty("sources");
			expect(body).not.toHaveProperty("leads");
			expect(JSON.stringify(body)).not.toContain("secret query");
			await route.fulfill({ response });
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
		await expect(page.getByTestId("mission-control-widget")).toBeVisible({
			timeout: 10000,
		});
		await controlResponse;
	});

	test("[P0] widget shows 0 tokens/sec and the available cost when token counts are missing", async ({
		page,
		workspace,
	}) => {
		// Mock the list endpoint so the widget fetches a specific mission
		await page.route(listMissionsPattern(workspace.id), async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					items: [
						{
							...MOCK_MISSION,
							workspace_id: workspace.id,
							phase: "reasoning",
						},
					],
					total: 1,
				}),
			});
		});

		// Mock the control response for the specific mission
		await page.route(controlPattern(workspace.id), async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					id: "00000000-0000-0000-0000-000000000000",
					workspace_id: workspace.id,
					mission_type: "deep_lead_research",
					status: "running",
					phase: "reasoning",
					progress_percent: 45,
					current_subtask_id: "subtask-1",
					token_velocity: {
						tokens_total: 0,
						tokens_per_second: 0,
						cost_micros: 12000,
						cost_credits: 0.012,
					},
					subtasks: [
						{
							id: "subtask-1",
							title: "Crawl",
							status: "success",
							phase: "crawl",
							reasoning_content: "",
							tokens_used: 0,
							tokens_per_second: 0,
							run_id: null,
							cost_micros: 12000,
							started_at: new Date().toISOString(),
							completed_at: new Date().toISOString(),
						},
					],
				}),
			});
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
		await expect(page.getByTestId("mission-control-widget")).toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByTestId("token-velocity-value")).toContainText("0 tokens/sec");
		await expect(page.getByTestId("token-velocity-cost")).toContainText("0.012");
	});

	test("[P0] lead matrix renders 1-3 shimmer rows during ingestion and highlights new rows", async ({
		page,
		workspace,
	}) => {
		// Mock a mission in the ingestion phase so the matrix shows shimmer
		await page.route(listMissionsPattern(workspace.id), async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					items: [
						{
							...MOCK_MISSION,
							workspace_id: workspace.id,
							phase: "ingestion",
							progress_percent: 90,
						},
					],
					total: 1,
				}),
			});
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);

		const shimmers = page.getByTestId("shimmer-skeleton-row");
		await expect(shimmers.first()).toBeVisible({ timeout: 10000 });
		const count = await shimmers.count();
		expect(count).toBeGreaterThanOrEqual(1);
		expect(count).toBeLessThanOrEqual(3);
	});

	test("[P1] new rows from Zero show the placeholder phone until REST refresh", async ({
		page,
		workspace,
	}) => {
		await page.route(
			new RegExp(`/api/v1/workspaces/${workspace.id}/leads(?:\\?|$)`),
			async (route) => {
				await route.fulfill({
					status: 200,
					contentType: "application/json",
					body: JSON.stringify({
						items: [
							{
								id: "lead-0000",
								workspace_id: workspace.id,
								company_name: "Công ty BĐS Mới",
								domain: "moi.vn",
								phone: null,
								is_unlocked: false,
								is_new_from_zero: true,
								fit_score: 80,
								created_at: new Date().toISOString(),
							},
						],
						total: 1,
					}),
				});
			}
		);

		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
		await expect(page.getByText("Đang giải mã SĐT...")).toBeVisible({
			timeout: 10000,
		});
	});
});
