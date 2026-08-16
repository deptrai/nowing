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
							id: "lead-1",
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
							id: "lead-2",
							company_name: "Công ty TNHH BĐS An Phú",
							title: "Cần thuê kho xưởng 1000m2 Bình Dương",
							source: "facebook",
							phone: "0987654321",
							fit_score: 85,
							location: "Thuận An, Bình Dương",
							price: "50 Triệu/tháng",
							created_at: new Date().toISOString(),
						},
					],
					total: 2,
					limit: 20,
					offset: 0,
				}),
			});
		});
	});

	test("should redirect /leads to /new-chat?mode=leads", async ({ page, workspace }) => {
		await page.goto(`/dashboard/${workspace.id}/leads`);
		await expect(page).toHaveURL(new RegExp(`/dashboard/${workspace.id}/new-chat\\?mode=leads`));
	});

	test("should render 2-panel split canvas with resizer and data matrix on new-chat", async ({
		page,
		workspace,
	}) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);

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

		await page.click("[data-testid='lead-row-lead-1']");
		await expect(page.locator("[data-testid='lead-detail-flyout-drawer']")).toBeVisible();
		await expect(page.locator("[data-testid='lead-detail-flyout-drawer']")).toContainText(
			"Nguyễn Văn Hùng"
		);
	});
});
