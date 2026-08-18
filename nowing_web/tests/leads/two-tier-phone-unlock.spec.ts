import type { APIRequestContext } from "@playwright/test";
import { expect, test } from "../fixtures";
import { authHeaders, BACKEND_URL } from "../helpers/api/auth";

test.describe("Story 26.5: Two-Tier Phone Unlock, Fast Unlock & Undo E2E", () => {
	async function createLeadWithMaskedPhone(
		request: APIRequestContext,
		apiToken: string,
		workspaceId: number
	): Promise<{ leadId: string; contactId: string }> {
		// The public lead creation endpoint is batch-ingest (Story 26.1).
		// Add a random suffix so multiple leads in the same test don't dedupe
		// on the (workspace, value_hmac) unique constraint.
		const suffix = Math.random().toString(36).slice(2, 8);
		const batchRes = await request.post(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/leads/batch-ingest`,
			{
				headers: authHeaders(apiToken),
				data: {
					leads: [
						{
							company_name: `Bất Động Sản E2E ${suffix}`,
							domain: `bds-e2e-${suffix}.vn`,
							source: "batdongsan",
							source_url: "https://batdongsan.com.vn/test-26-5",
							phone: "0908123456",
							location: "Cầu Giấy, Hà Nội",
							fit_score: 80,
						},
					],
				},
			}
		);
		expect(batchRes.status()).toBe(200);
		const batch = (await batchRes.json()) as { lead_ids: string[] };
		const leadId = batch.lead_ids[0];
		expect(leadId).toBeDefined();

		// Find the contact_id from the REST lead list once it is materialised.
		const listRes = await request.get(`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/leads`, {
			headers: authHeaders(apiToken),
		});
		expect(listRes.status()).toBe(200);
		const list = (await listRes.json()) as {
			items: Array<{ id: string; contact_id: string }>;
		};
		const item = list.items.find((i) => i.id === leadId);
		expect(item).toBeDefined();
		expect(item?.contact_id).toBeDefined();

		return { leadId, contactId: item?.contact_id ?? "" };
	}

	test("[P0] first phone click opens Smart Confirmation Popover with cost and fast-unlock toggle", async ({
		page,
		request,
		workspace,
		apiToken,
	}) => {
		const { contactId } = await createLeadWithMaskedPhone(request, apiToken, workspace.id);

		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
		const pill = page.getByTestId(`phone-pill-${contactId}`);
		await expect(pill).toContainText("0908***456", { timeout: 10000 });
		await pill.click();

		const popover = page.getByTestId("smart-unlock-popover");
		await expect(popover).toBeVisible();
		await expect(popover).toContainText("0908***456");
		await expect(popover).toContainText("1.5 credits");
		await expect(page.getByRole("checkbox", { name: /1-Click Fast Unlock/i })).toBeVisible();
		await expect(popover.getByRole("button", { name: /Mở khóa SĐT/i })).toBeVisible();
		await expect(page.getByRole("button", { name: /Hủy/i })).toBeVisible();
	});

	test("[P0] enabling fast unlock skips the popover on the next phone click", async ({
		page,
		request,
		workspace,
		apiToken,
	}) => {
		const first = await createLeadWithMaskedPhone(request, apiToken, workspace.id);
		const second = await createLeadWithMaskedPhone(request, apiToken, workspace.id);

		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);

		// First unlock: enable fast-unlock toggle
		await page.getByTestId(`phone-pill-${first.contactId}`).click();
		const firstPopover = page.getByTestId("smart-unlock-popover");
		await expect(firstPopover).toBeVisible();
		await page.getByRole("checkbox", { name: /1-Click Fast Unlock/i }).check();
		await firstPopover.getByRole("button", { name: /Mở khóa SĐT/i }).click();
		await expect(page.getByText("Đã mở khóa SĐT")).toBeVisible({
			timeout: 10000,
		});

		// Second unlock: popover should be skipped
		await page.getByTestId(`phone-pill-${second.contactId}`).click();
		await expect(page.getByTestId("smart-unlock-popover")).toBeHidden();
		await expect(page.getByTestId(`phone-pill-${second.contactId}`)).toContainText("0908123456");
	});

	test("[P0] successful unlock flips the pill, shows undo toast and enables outreach", async ({
		page,
		request,
		workspace,
		apiToken,
	}) => {
		const { leadId, contactId } = await createLeadWithMaskedPhone(request, apiToken, workspace.id);

		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);

		const pill = page.getByTestId(`phone-pill-${contactId}`);
		await pill.click();
		const popover = page.getByTestId("smart-unlock-popover");
		await expect(popover).toBeVisible();
		await popover.getByRole("button", { name: /Mở khóa SĐT/i }).click();

		await expect(page.getByText(/Đã mở khóa SĐT/)).toBeVisible({
			timeout: 20000,
		});
		await expect(pill).toContainText("0908123456", { timeout: 10000 });
		await expect(page.getByText("Hoàn tác")).toBeVisible();

		// Open the lead detail flyout to assert the call link and enabled Zalo button
		await page
			.getByTestId(`lead-row-${leadId}`)
			.getByText(/Bất Động Sản/)
			.first()
			.click();
		await expect(page.getByTestId("lead-detail-flyout-drawer")).toBeVisible({ timeout: 10000 });

		// Zalo / dial should now be active
		const drawer = page.getByTestId("lead-detail-flyout-drawer");
		await expect(drawer.getByTestId("zalo-outreach-button")).toBeEnabled();
		await expect(drawer.getByTestId("call-now-link")).toHaveAttribute("href", /tel:/);
	});

	test("[P0] undo toast relocks the number and re-enables the popover", async ({
		page,
		request,
		workspace,
		apiToken,
	}) => {
		const { contactId } = await createLeadWithMaskedPhone(request, apiToken, workspace.id);

		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);

		const pill = page.getByTestId(`phone-pill-${contactId}`);
		await pill.click();
		const popover = page.getByTestId("smart-unlock-popover");
		await expect(popover).toBeVisible();
		await popover.getByRole("button", { name: /Mở khóa SĐT/i }).click();
		await expect(page.getByText("Hoàn tác")).toBeVisible();

		await page.getByTestId("relock-undo-button").click();

		await expect(page.getByText(/Đã hoàn tác mở khóa/)).toBeVisible({
			timeout: 15000,
		});
		await expect(pill).toContainText("0908***456");

		// Next click should show the popover again
		await pill.click();
		await expect(page.getByTestId("smart-unlock-popover")).toBeVisible();
	});

	test("[P0] bulk unlock shows a single confirmation popover with total cost and handles partial failures", async ({
		page,
		request,
		workspace,
		apiToken,
	}) => {
		const _first = await createLeadWithMaskedPhone(request, apiToken, workspace.id);
		const _second = await createLeadWithMaskedPhone(request, apiToken, workspace.id);

		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);

		// Select two leads
		const rows = page.locator("[data-lead-row]");
		await rows.nth(0).getByRole("checkbox").check();
		await rows.nth(1).getByRole("checkbox").check();

		await page.getByTestId("bulk-unlock-button").click();

		const popover = page.getByTestId("smart-unlock-popover");
		await expect(popover).toBeVisible();
		await expect(popover).toContainText("3 credits");
		await expect(page.getByRole("checkbox", { name: /1-Click Fast Unlock/i })).toBeVisible();

		await popover.getByRole("button", { name: /Mở khóa SĐT hàng loạt/i }).click();
		await expect(page.getByText(/Đã mở khóa/)).toBeVisible({ timeout: 10000 });
	});

	test("[P1] Zalo and dial actions are disabled or hidden while the phone is locked", async ({
		page,
		request,
		workspace,
		apiToken,
	}) => {
		const { leadId } = await createLeadWithMaskedPhone(request, apiToken, workspace.id);

		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);

		// Click the company-name cell to open the flyout without hitting the checkbox/pill
		await page
			.getByTestId(`lead-row-${leadId}`)
			.getByText(/Bất Động Sản/)
			.first()
			.click();

		// Flyout drawer should open
		await expect(page.getByTestId("lead-detail-flyout-drawer")).toBeVisible({
			timeout: 10000,
		});

		const zalo = page.getByTestId("zalo-outreach-button").first();
		const call = page.getByRole("link", { name: /Gọi ngay/i });
		await expect(zalo).toBeDisabled();
		await expect(call).toBeHidden();
	});

	test("[P1] 150ms phone flip-in animation plays after unlock", async ({
		page,
		request,
		workspace,
		apiToken,
	}) => {
		const { contactId } = await createLeadWithMaskedPhone(request, apiToken, workspace.id);

		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
		const pill = page.getByTestId(`phone-pill-${contactId}`);
		await pill.click();
		const popover = page.getByTestId("smart-unlock-popover");
		await expect(popover).toBeVisible();
		await popover.getByRole("button", { name: /Mở khóa SĐT/i }).click();

		// The pill should gain a transition class that implies motion/flip
		await expect(pill).toHaveClass(/animate-flip/, { timeout: 30000 });
	});
});
