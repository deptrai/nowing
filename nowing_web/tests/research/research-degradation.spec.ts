import { expect, test } from "@playwright/test";
import { acquireTestToken, authHeaders, BACKEND_URL } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

type RunDetail = {
	id: string;
	status: string;
	output_text: string | null;
};

test.describe("Research degradation — 9.1a", () => {
	let token: string;
	let workspace: { id: number; name: string };

	test.beforeEach(async ({ request }) => {
		token = await acquireTestToken(request);
		workspace = await createWorkspace(request, token, `E2E Research ${Date.now()}`);
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, token, workspace.id);
	});

	test("should surface engine_unavailable in the playground without crashing", async ({
		page,
		request,
	}) => {
		// Deep research defaults to async. With CHAINLENS_API_KEY empty, the
		// executor degrades to engine_unavailable and falls back to the workspace KB.
		const response = await request.post(
			`${BACKEND_URL}/api/v1/workspaces/${workspace.id}/scrapers/chainlens/research`,
			{
				headers: authHeaders(token),
				data: {
					query: "self-host deep research degradation test",
					mode: "balanced",
				},
			}
		);

		// Sync mode (200) returns the completed run inline and sets X-Run-Id;
		// async mode (202) returns a run id in the body. Both are valid.
		expect([200, 202]).toContain(response.status());
		const responseBody = (await response.json()) as { run_id?: string };
		const xRunId = response.headers()["x-run-id"];
		const prefixedRunId = responseBody.run_id ?? xRunId;
		expect(prefixedRunId).toBeDefined();
		const runId = (prefixedRunId as string).replace(/^run_/, "");

		// Poll the run until it reaches a terminal state.
		let run: RunDetail | null = null;
		let terminal = false;
		for (let i = 0; i < 20 && !terminal; i++) {
			await page.waitForTimeout(250);
			const runResponse = await request.get(
				`${BACKEND_URL}/api/v1/workspaces/${workspace.id}/scrapers/runs/${runId}`,
				{
					headers: authHeaders(token),
				}
			);
			expect(runResponse.ok()).toBe(true);
			run = (await runResponse.json()) as RunDetail;
			terminal = run.status !== "running";
		}

		expect(run).not.toBeNull();
		if (run === null) throw new Error("run did not reach terminal state");
		expect(run.status).toBe("success");

		const output = run.output_text
			? (JSON.parse(run.output_text) as Record<string, unknown>)
			: null;
		expect(output).not.toBeNull();
		if (output === null) throw new Error("run output is empty");
		expect(output.status).toBe("engine_unavailable");
		expect(output.degraded).toBe(true);
		expect(output.degradation_reason).toMatch(
			/not_configured|fallback_kb|unreachable|upstream_error/
		);

		// Open the runs page and inspect the persisted output.
		await page.goto(`/dashboard/${workspace.id}/playground/runs`);
		await expect(page.getByText("chainlens.research")).toBeVisible();

		// Expand the run row.
		await page.getByText("chainlens.research").first().click();

		// Wait for the output panel and verify the degraded state is rendered.
		await expect(page.getByRole("heading", { name: /Output/i })).toBeVisible();
		await page.getByRole("tab", { name: "JSON" }).click();
		await expect(page.getByText("engine_unavailable").first()).toBeVisible();
		await expect(
			page.getByText(/not_configured|fallback_kb|unreachable|upstream_error/).first()
		).toBeVisible();

		// No Next.js error overlay.
		await expect(page.getByText(/Application error/i)).toHaveCount(0);
	});
});
