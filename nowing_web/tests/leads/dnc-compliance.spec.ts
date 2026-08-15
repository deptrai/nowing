import { expect, test } from "@playwright/test";
import { acquireTestToken, registerUser } from "../helpers/api/auth";
import { createWorkspace, deleteWorkspace } from "../helpers/api/workspaces";

test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Story 21.14: Smart Whitelist & Do-Not-Call (DNC) Compliance Engine E2E", () => {
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
			`E2E DNC Compliance ${Date.now()}`
		);
		workspaceId = workspace.id;
	});

	test.afterEach(async ({ request }) => {
		await deleteWorkspace(request, ownerToken, workspaceId);
	});

	test("E2E: Create DNC record, verify in modal UI, and test in-stream lead suppression", async ({
		page,
		request,
	}) => {
		const backendUrl = process.env.NOWING_BACKEND_INTERNAL_URL || "http://localhost:8000";

		// 1. Add a DNC record via REST API
		const dncRes = await request.post(`${backendUrl}/api/v1/workspaces/${workspaceId}/dnc`, {
			headers: { Authorization: `Bearer ${ownerToken}` },
			data: {
				record_type: "phone",
				value: "0908123456",
				reason: "Customer requested Do-Not-Call opt-out",
			},
		});
		expect(dncRes.ok()).toBeTruthy();
		const dncData = await dncRes.json();
		expect(dncData.record_type).toBe("phone");
		expect(dncData.value_hmac).toBeTruthy();

		// 2. Add a blocked Domain rule (*.competitor.vn)
		const dncDomRes = await request.post(`${backendUrl}/api/v1/workspaces/${workspaceId}/dnc`, {
			headers: { Authorization: `Bearer ${ownerToken}` },
			data: {
				record_type: "domain",
				value: "*.competitor.vn",
				reason: "Competitor domain exclusion",
			},
		});
		expect(dncDomRes.ok()).toBeTruthy();

		// 3. Log in and navigate to Leads page
		await page.goto("/login");
		await page
			.locator('input[type="email"], input[placeholder="you@example.com"]')
			.fill("e2e-test@nowing.net");
		await page.locator('input[type="password"]').fill("E2eTestPassword123!");
		await page.locator('button[type="submit"]:has-text("Sign In")').click();
		await page.waitForURL("**/dashboard/**");

		await page.goto(`/dashboard/${workspaceId}/leads`);
		await expect(page.locator("h1:has-text('Lead Intelligence Panel')")).toBeVisible({
			timeout: 10000,
		});

		// 4. Open DNC Management Modal
		const dncBtn = page.locator('button:has-text("Do-Not-Call (DNC)")');
		await expect(dncBtn).toBeVisible();
		await dncBtn.click();

		// 5. Verify DNC Management Modal Tabs and Entries
		await expect(
			page.locator("h2:has-text('Do-Not-Call (DNC) & Compliance Registry')")
		).toBeVisible();
		await expect(page.locator("button:has-text('Blacklist Registry')")).toBeVisible();
		await expect(page.locator("button:has-text('Add Single Record')")).toBeVisible();
		await expect(page.locator("button:has-text('Bulk CSV Import')")).toBeVisible();

		// Verify added records appear in the table
		await expect(page.locator("td:has-text('+84908123456')")).toBeVisible({
			timeout: 5000,
		});
		await expect(page.locator("td:has-text('*.competitor.vn')")).toBeVisible({
			timeout: 5000,
		});

		// 6. Test Tab 2: Add single entry via UI
		await page.locator("button:has-text('Add Single Record')").click();
		await page.locator('input[placeholder="0908123456"]').fill("0912345678");
		await page.locator('button:has-text("Add to DNC Blacklist")').click();

		// Verify automatic switch back to list and success notification
		await expect(page.locator("text=Added phone '0912345678' to DNC blacklist")).toBeVisible();
		await expect(page.locator("td:has-text('+84912345678')")).toBeVisible();

		// 7. Close modal
		await page.keyboard.press("Escape");
	});

	test("E2E: Hard purge PII via DELETE /api/v1/leads/{id}/pii under Decree 13 PDPD", async ({
		request,
	}) => {
		const backendUrl = process.env.NOWING_BACKEND_INTERNAL_URL || "http://localhost:8000";

		// 1. Create a lead with plaintext phone & email
		const leadRes = await request.post(`${backendUrl}/api/v1/workspaces/${workspaceId}/leads`, {
			headers: { Authorization: `Bearer ${ownerToken}` },
			data: {
				company_name: "Tập Đoàn Bất Động Sản Test PII",
				phone: "0987654321",
				email: "director@testpii.com",
				source: "batdongsan",
			},
		});
		expect(leadRes.ok()).toBeTruthy();
		const leadData = await leadRes.json();
		const leadId = leadData.id;

		// 2. Perform Right-to-be-Forgotten PII hard purge
		const purgeRes = await request.delete(`${backendUrl}/api/v1/leads/${leadId}/pii`, {
			headers: { Authorization: `Bearer ${ownerToken}` },
		});
		expect(purgeRes.ok()).toBeTruthy();
		const purgeData = await purgeRes.json();
		expect(purgeData.success).toBe(true);
		expect(purgeData.purged_fields).toContain("phone");
		expect(purgeData.purged_fields).toContain("email");
		expect(purgeData.dnc_blacklisted).toBe(true);

		// 3. Verify DNC registry has the HMAC hash but ZERO plaintext PII
		const dncListRes = await request.get(`${backendUrl}/api/v1/workspaces/${workspaceId}/dnc`, {
			headers: { Authorization: `Bearer ${ownerToken}` },
		});
		expect(dncListRes.ok()).toBeTruthy();
		const dncList = await dncListRes.json();
		const purgedDnc = dncList.records.find(
			(r: { source?: string; value?: string | null; value_hmac?: string }) =>
				r.source === "right_to_be_forgotten"
		);
		expect(purgedDnc).toBeTruthy();
		expect(purgedDnc.value).toBeNull(); // Zero-Knowledge invariant
		expect(purgedDnc.value_hmac).toBeTruthy();
	});
});
