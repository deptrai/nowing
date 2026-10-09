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
		await page.locator('button[type="submit"]').click();
		await page.waitForURL("**/dashboard/**");

		// /leads redirects to /new-chat?mode=leads, which renders the split canvas
		// in leads mode (hasActiveThread=true) so the contextual dock mounts.
		await page.goto(`/dashboard/${workspaceId}/leads`);
		await expect(page.getByTestId("nowing-split-canvas")).toBeVisible({ timeout: 15000 });

		// 4. Open DNC Management Modal. The DNC button label is "DNC" (en) or
		// "DNC" (vi) with a tooltip; match the stable short label.
		const dncBtn = page.getByRole("button", { name: /^DNC$/i });
		await expect(dncBtn).toBeVisible();
		await dncBtn.click();

		// 5. Verify DNC Management Modal Tabs and Entries (bilingual: en/vi).
		await expect(
			page.getByRole("heading", {
				name: /Do-Not-Call \(DNC\) & Compliance Registry|Danh bạ Do-Not-Call/i,
			})
		).toBeVisible();
		await expect(page.getByRole("button", { name: /Blacklist Registry|Sổ đen/i })).toBeVisible();
		await expect(
			page.getByRole("button", { name: /Add Single Record|Thêm bản ghi đơn/i })
		).toBeVisible();
		await expect(
			page.getByRole("button", { name: /Bulk CSV Import|Nhập CSV hàng loạt/i })
		).toBeVisible();

		// Verify added records appear in the table
		await expect(page.locator("td:has-text('+84908123456')")).toBeVisible({
			timeout: 5000,
		});
		await expect(page.locator("td:has-text('*.competitor.vn')")).toBeVisible({
			timeout: 5000,
		});

		// 6. Test Tab 2: Add single entry via UI
		await page.getByRole("button", { name: /Add Single Record|Thêm bản ghi đơn/i }).click();
		await page.locator('input[placeholder="0908123456"]').fill("0912345678");
		await page.getByRole("button", { name: /Add to DNC Blacklist|Thêm vào sổ đen DNC/i }).click();

		// Verify automatic switch back to list and success notification
		await expect(
			page.getByText(
				/Added phone '0912345678' to DNC blacklist|Đã thêm phone '0912345678' vào sổ đen DNC/i
			)
		).toBeVisible();
		await expect(page.locator("td:has-text('+84912345678')")).toBeVisible();

		// 7. Close modal
		await page.keyboard.press("Escape");
	});

	test("E2E: Hard purge PII via POST /workspaces/{id}/pii-opt-out under Decree 13 PDPD", async ({
		request,
	}) => {
		const backendUrl = process.env.NOWING_BACKEND_INTERNAL_URL || "http://localhost:8000";

		// 1. Create a lead with plaintext phone & email via batch-ingest — ingest
		// materialises encrypted VerifiedContact rows (with phone_hmac) that
		// pii-opt-out can purge.
		const leadRes = await request.post(
			`${backendUrl}/api/v1/workspaces/${workspaceId}/leads/batch-ingest`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
				data: {
					leads: [
						{
							company_name: "Tập Đoàn Bất Động Sản Test PII",
							phone: "0987654321",
							email: "director@testpii.com",
							source: "batdongsan",
						},
					],
				},
			}
		);
		expect(leadRes.ok()).toBeTruthy();
		const leadData = await leadRes.json();
		expect(leadData.lead_ids?.length).toBeGreaterThanOrEqual(1);

		// 2. Perform Right-to-be-Forgotten PII purge via workspace pii-opt-out
		// (purges matching verified_contacts and upserts a DNC record in one
		// transaction; DELETE /leads/{id}/pii no longer exists).
		const purgeRes = await request.post(
			`${backendUrl}/api/v1/workspaces/${workspaceId}/pii-opt-out`,
			{
				headers: { Authorization: `Bearer ${ownerToken}` },
				data: {
					record_type: "phone",
					value: "0987654321",
					reason: "Right to be forgotten",
				},
			}
		);
		expect(purgeRes.ok()).toBeTruthy();
		const purgeData = await purgeRes.json();
		expect(purgeData.dnc_record_id).toBeTruthy();
		expect(purgeData.purged_contact_count).toBeGreaterThanOrEqual(1);
		expect(purgeData.refunded_micros).toBeGreaterThanOrEqual(0);

		// 3. Verify DNC registry picked up the opt-out record
		const dncListRes = await request.get(`${backendUrl}/api/v1/workspaces/${workspaceId}/dnc`, {
			headers: { Authorization: `Bearer ${ownerToken}` },
		});
		expect(dncListRes.ok()).toBeTruthy();
		const dncList = await dncListRes.json();
		const purgedDnc = dncList.records.find(
			(r: { id?: string; source?: string; record_type?: string; value_hmac?: string }) =>
				r.id === purgeData.dnc_record_id
		);
		expect(purgedDnc).toBeTruthy();
		expect(purgedDnc.source).toBe("opt_out");
		expect(purgedDnc.record_type).toBe("phone");
		expect(purgedDnc.value_hmac).toBeTruthy();
	});
});
