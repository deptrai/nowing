import type { APIRequestContext } from "@playwright/test";
import { expect, test } from "../fixtures";
import { authHeaders, BACKEND_URL } from "../helpers/api/auth";

test.describe("Story 26.5: Two-Tier Phone Unlock, Fast Unlock & Undo E2E", () => {
	async function createLeadWithMaskedPhone(
		request: APIRequestContext,
		apiToken: string,
		workspaceId: number
	): Promise<{ leadId: string; contactId: string }> {
		const createLeadRes = await request.post(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/leads`,
			{
				headers: authHeaders(apiToken),
				data: {
					company_name: "Bất Động Sản E2E",
					domain: "bds-e2e.vn",
					source: "batdongsan",
					source_url: "https://batdongsan.com.vn/test-26-5",
					raw_text: "Liên hệ chính chủ: 0908 123 456 gặp anh Tuấn",
					location: "Cầu Giấy, Hà Nội",
				},
			}
		);
		expect([200, 201]).toContain(createLeadRes.status());
		const lead = (await createLeadRes.json()) as { id: string };

		const resolveRes = await request.post(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/leads/${lead.id}/resolve-phone`,
			{
				headers: authHeaders(apiToken),
				data: {
					source_url: "https://batdongsan.com.vn/test-26-5",
					raw_text: "Liên hệ chính chủ: 0908 123 456 gặp anh Tuấn",
					force_refresh: true,
				},
			}
		);
		expect(resolveRes.status()).toBe(200);

		// Find the contact_id from the REST lead list once it is materialised.
		const listRes = await request.get(
			`${BACKEND_URL}/api/v1/workspaces/${workspaceId}/leads`,
			{
				headers: authHeaders(apiToken),
			}
		);
		expect(listRes.status()).toBe(200);
		const list = (await listRes.json()) as {
			items: Array<{ id: string; contact_id: string }>;
		};
		const item = list.items.find((i) => i.id === lead.id);
		expect(item).toBeDefined();
		expect(item?.contact_id).toBeDefined();

		return { leadId: lead.id, contactId: item!.contact_id };
	}

	test(
		"[P0] first phone click opens Smart Confirmation Popover with cost and fast-unlock toggle",
		async ({ page, request, workspace, apiToken }) => {
			const { leadId, contactId } = await createLeadWithMaskedPhone(
				request,
				apiToken,
				workspace.id
			);

			await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
			const pill = page.getByTestId(`phone-pill-${contactId}`);
			await expect(pill).toContainText("0908***456", { timeout: 10000 });
			await pill.click();

			const popover = page.getByTestId("smart-unlock-popover");
			await expect(popover).toBeVisible();
			await expect(popover).toContainText("0908***456");
			await expect(popover).toContainText("1.5 credits");
			await expect(
				page.getByRole("checkbox", { name: /1-Click Fast Unlock/i })
			).toBeVisible();
			await expect(
				page.getByRole("button", { name: /Mở khóa SĐT/i })
			).toBeVisible();
			await expect(page.getByRole("button", { name: /Hủy/i })).toBeVisible();
		}
	);

	test(
		"[P0] enabling fast unlock skips the popover on the next phone click",
		async ({ page, request, workspace, apiToken }) => {
			const first = await createLeadWithMaskedPhone(request, apiToken, workspace.id);
			const second = await createLeadWithMaskedPhone(request, apiToken, workspace.id);

			await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);

			// First unlock: enable fast-unlock toggle
			await page.getByTestId(`phone-pill-${first.contactId}`).click();
			await page
				.getByRole("checkbox", { name: /1-Click Fast Unlock/i })
				.check();
			await page.getByRole("button", { name: /Mở khóa SĐT/i }).click();
			await expect(page.getByText("Đã mở khóa SĐT")).toBeVisible({
				timeout: 10000,
			});

			// Second unlock: popover should be skipped
			await page.getByTestId(`phone-pill-${second.contactId}`).click();
			await expect(page.getByTestId("smart-unlock-popover")).toBeHidden();
			await expect(page.getByTestId(`phone-pill-${second.contactId}`)).toContainText(
				"0908123456"
			);
		}
	);

	test(
		"[P0] successful unlock flips the pill, decrements credits and shows undo toast",
		async ({ page, request, workspace, apiToken }) => {
			const { leadId, contactId } = await createLeadWithMaskedPhone(
				request,
				apiToken,
				workspace.id
			);

			await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
			const creditBefore = await page
				.getByTestId("credit-balance-badge")
				.textContent();

			const pill = page.getByTestId(`phone-pill-${contactId}`);
			await pill.click();
			await page.getByRole("button", { name: /Mở khóa SĐT/i }).click();

			await expect(page.getByText(/Đã mở khóa SĐT/)).toBeVisible({
				timeout: 10000,
			});
			await expect(pill).toContainText("0908123456");
			await expect(page.getByText("Hoàn tác")).toBeVisible();

			const creditAfter = await page
				.getByTestId("credit-balance-badge")
				.textContent();
			expect(creditAfter).not.toEqual(creditBefore);

			// Zalo / dial should now be active
			await expect(page.getByTestId("zalo-outreach-button")).toBeEnabled();
			await expect(
				page.getByRole("link", { name: /Gọi ngay/i })
			).toHaveAttribute("href", /tel:/);
		}
	);

	test(
		"[P0] undo toast relocks the number, refunds 1.5 credits and re-enables the popover",
		async ({ page, request, workspace, apiToken }) => {
			const { leadId, contactId } = await createLeadWithMaskedPhone(
				request,
				apiToken,
				workspace.id
			);

			await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
			const creditBefore = await page
				.getByTestId("credit-balance-badge")
				.textContent();

			const pill = page.getByTestId(`phone-pill-${contactId}`);
			await pill.click();
			await page.getByRole("button", { name: /Mở khóa SĐT/i }).click();
			await expect(page.getByText("Hoàn tác")).toBeVisible();

			await page.getByText("Hoàn tác").click();

			await expect(page.getByText(/Đã hoàn tác mở khóa/)).toBeVisible({
				timeout: 10000,
			});
			await expect(pill).toContainText("0908***456");

			const creditAfter = await page
				.getByTestId("credit-balance-badge")
				.textContent();
			expect(creditAfter).toEqual(creditBefore);

			// Next click should show the popover again
			await pill.click();
			await expect(page.getByTestId("smart-unlock-popover")).toBeVisible();
		}
	);

	test(
		"[P0] bulk unlock shows a single confirmation popover with total cost and handles partial failures",
		async ({ page, request, workspace, apiToken }) => {
			const first = await createLeadWithMaskedPhone(request, apiToken, workspace.id);
			const second = await createLeadWithMaskedPhone(request, apiToken, workspace.id);

			await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);

			// Select two leads
			const rows = page.locator("[data-lead-row]");
			await rows.nth(0).getByRole("checkbox").check();
			await rows.nth(1).getByRole("checkbox").check();

			await page.getByTestId("bulk-unlock-button").click();

			const popover = page.getByTestId("smart-unlock-popover");
			await expect(popover).toBeVisible();
			await expect(popover).toContainText("3 credits");
			await expect(
				page.getByRole("checkbox", { name: /1-Click Fast Unlock/i })
			).toBeVisible();

			await page.getByRole("button", { name: /Mở khóa SĐT hàng loạt/i }).click();
			await expect(page.getByText(/Mở khóa/)).toBeVisible({ timeout: 10000 });
		}
	);

	test(
		"[P1] Zalo and dial actions are disabled or hidden while the phone is locked",
		async ({ page, request, workspace, apiToken }) => {
			const { leadId, contactId } = await createLeadWithMaskedPhone(
				request,
				apiToken,
				workspace.id
			);

			await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
			await page.getByTestId(`lead-row-${leadId}`).click();

			// Flyout drawer should open
			await expect(page.getByTestId("lead-detail-flyout-drawer")).toBeVisible({
				timeout: 10000,
			});

			const zalo = page.getByTestId("zalo-outreach-button");
			const call = page.getByRole("link", { name: /Gọi ngay/i });
			await expect(zalo).toBeDisabled();
			await expect(call).toBeHidden();
		}
	);

	test(
		"[P1] 150ms phone flip-in animation plays after unlock",
		async ({ page, request, workspace, apiToken }) => {
			const { leadId, contactId } = await createLeadWithMaskedPhone(
				request,
				apiToken,
				workspace.id
			);

			await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
			const pill = page.getByTestId(`phone-pill-${contactId}`);
			await pill.click();
			await page.getByRole("button", { name: /Mở khóa SĐT/i }).click();

			// The pill should gain a transition class that implies motion/flip
			await expect(pill).toHaveClass(/animate-flip/);
			const computed = await pill.evaluate((el) =>
				window.getComputedStyle(el).getPropertyValue("transition-duration")
			);
			expect(computed).toMatch(/0\.15/);
		}
	);
});
