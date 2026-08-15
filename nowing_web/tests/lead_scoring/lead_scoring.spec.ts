import { expect, test } from "@playwright/test";
import { acquireTestToken, registerUser } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

// Lead scoring has no web UI yet; this E2E verifies the new REST
// contracts directly through the backend so the web app will not
// crash when it later consumes these responses.
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Lead scoring API", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		await registerUser(request, "e2e-test@nowing.net", "E2eTestPassword123!").catch(() => {
			// User may already exist in non-fresh databases.
		});
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(request, ownerToken, `E2E LeadScoring ${Date.now()}`);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("POST /workspaces/{id}/leads/score returns typed output without crashing", async ({ request }) => {
		const response = await request.post(
			`http://localhost:8000/api/v1/workspaces/${workspaceId}/leads/score`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
				data: {},
			}
		);
		expect(response.status()).toBe(200);
		const body = await response.json();
		expect(body).toHaveProperty("items");
		expect(body).toHaveProperty("cost_micros");
		expect(body).toHaveProperty("degraded");
	});

	test("GET /workspaces/{id}/leads/scores returns a list", async ({ request }) => {
		const response = await request.get(
			`http://localhost:8000/api/v1/workspaces/${workspaceId}/leads/scores`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
			}
		);
		expect(response.status()).toBe(200);
		const body = await response.json();
		expect(Array.isArray(body)).toBe(true);
	});

	test("PUT /workspaces/{id}/icp updates ICP criteria", async ({ request }) => {
		const response = await request.put(
			`http://localhost:8000/api/v1/workspaces/${workspaceId}/icp`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
				data: {
					target_industries: ["saas"],
					target_locations: ["us"],
					target_company_sizes: { min: 11, max: 50 },
					target_tech_stack: ["python"],
					weights: { fit: 0.5, intent: 0.5 },
				},
			}
		);
		expect(response.status()).toBe(200);
		const body = await response.json();
		expect(body.target_industries).toContain("saas");
	});
});
