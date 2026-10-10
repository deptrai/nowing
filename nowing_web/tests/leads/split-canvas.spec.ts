import { expect, test } from "../fixtures";

test.describe("Story 21.16: Nowing Split-View Canvas & Workspace Modernization", () => {
	test.beforeEach(async ({ page }) => {
		// Mock leads endpoint if needed for isolated E2E tests
		await page.route("**/workspaces/*/leads*", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					items: [
						{
							id: "11111111-1111-4111-8111-111111111111",
							workspace_id: 1,
							company_name: "Nguyễn Văn Hùng",
							title: "Bán nhà mặt tiền Thủ Đức 8.5 Tỷ",
							source: "batdongsan",
							phone: "0901234567",
							fit_score: 92,
							location: "Thủ Đức, TP.HCM",
							price: "8.5 Tỷ",
							created_at: new Date().toISOString(),
						},
						{
							id: "22222222-2222-4222-8222-222222222222",
							workspace_id: 1,
							company_name: "Công ty TNHH BĐS An Phú",
							title: "Cần thuê kho xưởng 1000m2 Bình Dương",
							source: "facebook",
							phone: "0987654321",
							fit_score: 85,
							location: "Thuận An, Bình Dương",
							price: "50 Triệu/tháng",
							created_at: new Date().toISOString(),
						},
						{
							id: "33333333-3333-4333-8333-333333333333",
							workspace_id: 1,
							company_name: "Công ty TNHH Websets Corp",
							title: "Webset verified lead Q7",
							source: "websets",
							phone: "0912345678",
							fit_score: 88,
							location: "Quận 7, TP.HCM",
							price: "3 Tỷ",
							created_at: new Date().toISOString(),
							extra_metadata: {
								websets: {
									district: { value: "Quận 7", groundingUrl: "https://example.com" },
								},
							},
						},
					],
					total: 3,
					limit: 20,
					offset: 0,
				}),
			});
		});
	});

	// The contextual right dock starts closed (dockOpenAtom default) — leads
	// mode shows a FloatingReopenPill until the user opens it.
	async function openDock(page: import("@playwright/test").Page) {
		// i18n: en "Open canvas" / vi "Mở canvas"; pill mounts async — waitFor avoids
		// the isVisible() race right after page.goto.
		const pill = page.getByRole("button", { name: /open canvas|mở canvas/i });
		const visible = await pill
			.waitFor({ state: "visible", timeout: 5000 })
			.then(() => true)
			.catch(() => false);
		if (visible) await pill.click();
	}

	test("should redirect /leads to /new-chat?mode=leads", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/leads`);
		await expect(page).toHaveURL(new RegExp(`/dashboard/${workspace.id}/new-chat\\?mode=leads`));
	});

	test("should render 2-panel split canvas with resizer and data matrix on new-chat", async ({
		page,
		workspace,
	}) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
		await openDock(page);

		// AC1: Split canvas panels exist
		await expect(page.locator("[data-testid='nowing-split-canvas']")).toBeVisible();
		await expect(page.locator("[data-testid='nowing-lead-matrix']")).toBeVisible();
		await expect(page.locator("[data-testid='split-canvas-resizer']")).toBeVisible();
	});

	test("should show floating bulk action bar when >= 2 leads are selected", async ({
		page,
		workspace,
	}) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
		await openDock(page);

		const checkboxes = page.locator("input[type='checkbox'][data-lead-checkbox]");
		await checkboxes.nth(0).check();
		await expect(page.locator("[data-testid='floating-bulk-action-bar']")).toBeHidden();

		await checkboxes.nth(1).check();
		await expect(page.locator("[data-testid='floating-bulk-action-bar']")).toBeVisible();
		await expect(page.locator("[data-testid='floating-bulk-action-bar']")).toContainText(
			"Đã chọn 2 leads"
		);
	});

	test("should open flyout detail drawer on row click", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
		await openDock(page);

		await page.locator("[data-testid^='lead-row-']").first().click();
		await expect(page.locator("[data-testid='lead-detail-flyout-drawer']")).toBeVisible();
		await expect(page.locator("[data-testid='lead-detail-flyout-drawer']")).toContainText(
			"Nguyễn Văn Hùng"
		);
	});

	test("Story 41.2: websets source filter shows only websets leads", async ({
		page,
		workspace,
	}) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
		await openDock(page);

		const matrix = page.locator("[data-testid='nowing-lead-matrix']");
		await expect(matrix).toBeVisible();
		await expect(page.locator("[data-testid^='lead-row-']")).toHaveCount(3);

		// Open source dropdown (trigger shows current option label "Tất cả nguồn"/"All sources")
		await page
			.getByRole("button", { name: /tất cả nguồn|all sources/i })
			.first()
			.click();
		await page.getByRole("button", { name: /ChainLens Websets/i }).click();

		await expect(page.locator("[data-testid^='lead-row-']")).toHaveCount(1);
		await expect(matrix).toContainText("Công ty TNHH Websets Corp");
		await expect(matrix).not.toContainText("Nguyễn Văn Hùng");

		// Open the websets lead → drawer shows unmapped enrichment cells
		await page.locator("[data-testid^='lead-row-']").first().click();
		await expect(page.locator("[data-testid='websets-enrichments-section']")).toBeVisible();
	});
});
