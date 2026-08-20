import { expect, test } from "../fixtures";

test.describe("Mission Control — deliverable download (26.9b)", () => {
	test("should render deliverables and download xlsx on click", async ({
		page,
		workspace,
	}) => {
		const listPattern = new RegExp(`/api/v1/workspaces/${workspace.id}/dsh/missions(?:\\?.*)?$`);
		const controlPattern = new RegExp(
			`/api/v1/workspaces/${workspace.id}/dsh/missions/[\\w-]+/control$`
		);
		const missionId = "00000000-0000-0000-0000-000000000003";
		const filename = "wide_research_output.xlsx";
		const downloadPattern = new RegExp(
			`/api/v1/workspaces/${workspace.id}/dsh/missions/${missionId}/deliverables/${filename}`
		);

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
							status: "success",
							phase: "terminal",
							progress_percent: 100,
							current_subtask_id: null,
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

		await page.route(controlPattern, async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					id: missionId,
					workspace_id: workspace.id,
					mission_type: "deep_lead_research",
					status: "success",
					phase: "terminal",
					progress_percent: 100,
					current_subtask_id: null,
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
							cost_micros: 12000,
							started_at: new Date().toISOString(),
							completed_at: new Date().toISOString(),
						},
						{
							id: "deliver",
							title: "Deliver",
							status: "success",
							phase: "deliver",
							reasoning_content: "",
							tokens_used: 0,
							tokens_per_second: 0,
							cost_micros: 0,
							started_at: new Date().toISOString(),
							completed_at: new Date().toISOString(),
						},
					],
					deliverables: [
						{
							type: "xlsx",
							filename,
							size: 10240,
							created_at: new Date().toISOString(),
							include_pii: false,
						},
					],
				}),
			});
		});

		await page.route(downloadPattern, async (route) => {
			await route.fulfill({
				status: 200,
				contentType:
					"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
				headers: {
					"Content-Disposition": `attachment; filename="${filename}"`,
				},
				body: Buffer.from("fake-xlsx-content"),
			});
		});

		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);

		await expect(page.getByTestId("mission-control-widget")).toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByTestId("mission-control-deliverables")).toBeVisible({
			timeout: 10000,
		});
		await expect(
			page.getByTestId(`mission-control-download-${filename}`)
		).toContainText(filename);

		const [download] = await Promise.all([
			page.waitForEvent("download"),
			page.getByTestId(`mission-control-download-${filename}`).click(),
		]);

		expect(download.suggestedFilename()).toBe(filename);
	});
});
