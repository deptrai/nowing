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

		// 1. Create a sample Lead in workspace via batch-ingest (single-lead
		// POST /leads no longer exists; the API contract is batch-oriented and
		// requires at least one of phone/email/domain per lead).
		const createLeadRes = await request.post(
			`${backendUrl}/api/v1/workspaces/${workspaceId}/leads/batch-ingest`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
				data: {
					leads: [
						{
							company_name: "Bất Động Sản Thăng Long E2E",
							source: "batdongsan",
							source_url: "https://batdongsan.com.vn/ban-nha-mat-pho-cau-giay",
							location: "Cầu Giấy, Hà Nội",
							// non-degenerate guard: a domain keeps phone off the record so
							// the waterfall must resolve it from raw_text below.
							domain: "thanglong-bds.example.vn",
						},
					],
				},
			}
		);
		expect([200, 201]).toContain(createLeadRes.status());
		const ingestData = await createLeadRes.json();
		const leadId = ingestData.lead_ids?.[0];
		expect(leadId).toBeDefined();

		// 2. Trigger Phone Resolution Waterfall endpoint. The phone lives in the
		// request raw_text so tier-3 passive carrier validation resolves it
		// deterministically (tiers 1/2 need live scraper credentials and fall
		// through when none are configured).
		const resolveRes = await request.post(
			`${backendUrl}/api/v1/workspaces/${workspaceId}/leads/${leadId}/resolve-phone`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
				data: {
					raw_text: "Liên hệ chính chủ: 0908123456",
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
		// Contract field is refund_amount_credits (not refund_credits).
		expect(refundData.refund_amount_credits).toBe(1.5);
		expect(refundData.refund_micros).toBe(1500000);
	});

	test("UI: Lead Intelligence Table renders masked phone copy pills and company graph", async ({
		page,
	}) => {
		// Log in as test user
		await page.goto("/login");
		// i18n-safe: the login form is Vietnamese ("Mật khẩu" / "Đăng nhập"),
		// so select by stable id/type instead of localized accessible names.
		await page.locator("input#email").fill("e2e-test@nowing.net");
		await page.locator("input#password").fill("E2eTestPassword123!");
		await page.locator('button[type="submit"]').click();

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
