import { expect, test } from "@playwright/test";
import { acquireTestToken, registerUser } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Story 21.13: Multi-Table Tabs & Send/Export Hub E2E", () => {
	let workspaceId: number;
	let ownerToken: string;

	test.beforeEach(async ({ request }) => {
		await registerUser(request, "e2e-test@nowing.net", "E2eTestPassword123!").catch(() => {
			// User may already exist
		});
		ownerToken = await acquireTestToken(request);
		const workspace = await createWorkspace(
			request,
			ownerToken,
			`E2E Tables & Export ${Date.now()}`
		);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("CRUD workspace tables and assign leads", async ({ request }) => {
		const backendUrl = process.env.NOWING_BACKEND_INTERNAL_URL || "http://localhost:8000";

		// 1. Create new table tab
		const createRes = await request.post(`${backendUrl}/api/v1/workspaces/${workspaceId}/tables`, {
			headers: { Authorization: `Bearer ${ownerToken}` },
			data: {
				name: "BĐS Quận 1 & 2",
				icon: "home",
				filter_preset: { source: "batdongsan", min_score: 75 },
				columns_config: { visible: ["company_name", "location", "phone"] },
			},
		});
		expect(createRes.status()).toBe(201);
		const table = await createRes.json();
		expect(table.name).toBe("BĐS Quận 1 & 2");
		expect(table.icon).toBe("home");
		const tableId = table.id;

		// 2. List tables
		const listRes = await request.get(`${backendUrl}/api/v1/workspaces/${workspaceId}/tables`, {
			headers: { Authorization: `Bearer ${ownerToken}` },
		});
		expect(listRes.status()).toBe(200);
		const tables = await listRes.json();
		expect(Array.isArray(tables)).toBe(true);
		expect(tables.some((t: { id: string }) => t.id === tableId)).toBe(true);

		// 3. Update table
		const updateRes = await request.patch(
			`${backendUrl}/api/v1/workspaces/${workspaceId}/tables/${tableId}`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
				data: {
					name: "BĐS TP. Thủ Đức",
					icon: "building",
				},
			}
		);
		expect(updateRes.status()).toBe(200);
		const updated = await updateRes.json();
		expect(updated.name).toBe("BĐS TP. Thủ Đức");
		expect(updated.icon).toBe("building");

		// 4. Assign leads to table
		const assignRes = await request.post(
			`${backendUrl}/api/v1/workspaces/${workspaceId}/tables/${tableId}/assign-leads`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
				data: {
					lead_ids: [],
				},
			}
		);
		expect(assignRes.status()).toBe(200);
		const assignData = await assignRes.json();
		expect(assignData.table_id).toBe(tableId);

		// 5. Delete table
		const deleteRes = await request.delete(
			`${backendUrl}/api/v1/workspaces/${workspaceId}/tables/${tableId}`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
			}
		);
		expect(deleteRes.status()).toBe(204);
	});

	test("Trigger CSV stream export with PII masking", async ({ request }) => {
		const backendUrl = process.env.NOWING_BACKEND_INTERNAL_URL || "http://localhost:8000";

		const exportRes = await request.post(
			`${backendUrl}/api/v1/workspaces/${workspaceId}/leads/export`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
				data: {
					export_type: "csv",
					mask_pii: true,
				},
			}
		);
		expect(exportRes.status()).toBe(200);
		expect(exportRes.headers()["content-type"]).toContain("text/csv");
		const csvText = await exportRes.text();
		expect(csvText).toContain("Company Name,Domain,Source,Industry");
	});

	test("Trigger cloud connector export job and poll status", async ({ request }) => {
		const backendUrl = process.env.NOWING_BACKEND_INTERNAL_URL || "http://localhost:8000";

		const exportRes = await request.post(
			`${backendUrl}/api/v1/workspaces/${workspaceId}/leads/export`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
				data: {
					export_type: "lark_base",
					mask_pii: true,
					target_config: {
						app_token: "bascnTestApp123",
						table_id: "tblTestTable456",
					},
				},
			}
		);
		expect(exportRes.status()).toBe(200);
		const jobData = await exportRes.json();
		expect(jobData.export_type).toBe("lark_base");
		expect(jobData.job_id).toBeDefined();

		// Poll status
		const statusRes = await request.get(
			`${backendUrl}/api/v1/workspaces/${workspaceId}/leads/export/jobs/${jobData.job_id}`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
			}
		);
		expect(statusRes.status()).toBe(200);
		const polled = await statusRes.json();
		expect(polled.job_id).toBe(jobData.job_id);
	});
});
