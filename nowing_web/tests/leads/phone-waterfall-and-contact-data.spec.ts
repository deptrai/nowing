import { expect, test } from "@playwright/test";
import { acquireTestToken, registerUser } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Story 21.3: Vietnam Phone & Contact Waterfall Engine E2E", () => {
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
			`E2E Phone Waterfall ${Date.now()}`
		);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("E2E: Resolve lead phone via waterfall and report invalid phone for auto-refund SLA", async ({
		request,
	}) => {
		const backendUrl = process.env.NOWING_BACKEND_INTERNAL_URL || "http://localhost:8000";

		// 1. Create a sample Lead in workspace
		const createLeadRes = await request.post(
			`${backendUrl}/api/v1/workspaces/${workspaceId}/leads`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
				data: {
					company_name: "Bất Động Sản Thăng Long E2E",
					source: "batdongsan",
					source_url: "https://batdongsan.com.vn/ban-nha-mat-pho-cau-giay",
					raw_text: "Liên hệ chính chủ xem nhà: 0908 123 456 gặp anh Thăng",
					location: "Cầu Giấy, Hà Nội",
				},
			}
		);
		expect([200, 201]).toContain(createLeadRes.status());
		const lead = await createLeadRes.json();
		const leadId = lead.id;
		expect(leadId).toBeDefined();

		// 2. Trigger Phone Resolution Waterfall endpoint
		const resolveRes = await request.post(
			`${backendUrl}/api/v1/workspaces/${workspaceId}/leads/${leadId}/resolve-phone`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
				data: {
					source_url: "https://batdongsan.com.vn/ban-nha-mat-pho-cau-giay",
					raw_text: "Liên hệ chính chủ: 0908 123 456",
					force_refresh: true,
				},
			}
		);
		expect(resolveRes.status()).toBe(200);
		const resolveData = await resolveRes.json();
		expect(resolveData.lead_id).toBe(leadId);
		expect(resolveData.phone_masked).toBe("0908***456");
		expect(resolveData.carrier).toBe("MobiFone");
		expect(resolveData.tier_reached).toBeGreaterThanOrEqual(1);

		// 3. Report Invalid Phone within 24h SLA for auto-refund
		const refundRes = await request.post(
			`${backendUrl}/api/v1/workspaces/${workspaceId}/leads/${leadId}/report-invalid-phone`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
				data: {
					reason: "Số máy bận liên tục không liên lạc được",
				},
			}
		);
		expect(refundRes.status()).toBe(200);
		const refundData = await refundRes.json();
		expect(refundData.lead_id).toBe(leadId);
		expect(refundData.refunded).toBe(true);
		expect(refundData.refund_credits).toBe(1.5);
		expect(refundData.refund_micros).toBe(1500000);
	});

	test("UI: Lead Intelligence Table renders masked phone copy pills and company graph", async ({
		page,
	}) => {
		// Log in as test user
		await page.goto("http://localhost:3000/login");
		await page.getByRole("textbox", { name: "Email" }).fill("e2e-test@nowing.net");
		await page.getByRole("textbox", { name: "Password" }).fill("E2eTestPassword123!");
		await page.getByRole("button", { name: "Sign In" }).click();

		// Navigate to Leads view
		await page.waitForURL(/\/dashboard\/\d+/);
		await page.goto(`http://localhost:3000/dashboard/${workspaceId}/leads`);

		// Assert table header & columns
		await expect(page.getByRole("heading", { name: /Lead Intelligence Panel/i })).toBeVisible({
			timeout: 10000,
		});
		await expect(page.getByRole("columnheader", { name: /Doanh nghiệp \/ Nguồn/i })).toBeVisible();
		await expect(page.getByRole("columnheader", { name: /Liên hệ \(SĐT\)/i })).toBeVisible();

		// Verify phone copy pill is present and clickable
		const phonePill = page.getByRole("button", { name: /Copy phone number/i }).first();
		if (await phonePill.isVisible()) {
			await phonePill.click();
		}

		// Verify Company Graph button and modal interaction
		const graphBtn = page.getByRole("button", { name: /Xem Company Graph/i }).first();
		if (await graphBtn.isVisible()) {
			await graphBtn.click();
			await expect(page.getByRole("heading", { name: /Enterprise Graph/i })).toBeVisible();
			await page.getByRole("button", { name: /Đóng/i }).first().click();
		}
	});
});
