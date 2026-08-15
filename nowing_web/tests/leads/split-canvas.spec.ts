import { expect, test } from "@playwright/test";

test.describe("Story 21.16: Origami Split-View Canvas & Workspace Modernization", () => {
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

	test("should render 2-panel split canvas with resizer, chat co-pilot and data matrix", async ({
		page,
	}) => {
		// TDD Green phase verification
		await page.goto("/dashboard/1/leads");

		// AC1: Split canvas panels exist
		await expect(page.locator("[data-testid='origami-split-canvas']")).toBeVisible();
		await expect(page.locator("[data-testid='origami-chat-copilot']")).toBeVisible();
		await expect(page.locator("[data-testid='origami-lead-matrix']")).toBeVisible();
		await expect(page.locator("[data-testid='split-canvas-resizer']")).toBeVisible();
	});

	test("should toggle 3-Mode switcher (Leads, Research, Scrapers) smoothly", async ({
		page,
	}) => {
		// TDD Green phase verification
		await page.goto("/dashboard/1/leads");

		const switcher = page.locator("[data-testid='mode-switcher']");
		await expect(switcher).toBeVisible();

		// Click Research mode
		await page.click("[data-testid='mode-tab-research']");
		await expect(page.locator("[data-testid='mode-tab-research']")).toHaveAttribute(
			"data-state",
			"active"
		);

		// Click Scrapers mode
		await page.click("[data-testid='mode-tab-scrapers']");
		await expect(page.locator("[data-testid='mode-tab-scrapers']")).toHaveAttribute(
			"data-state",
			"active"
		);
	});

	test("should show floating bulk action bar when >= 2 leads are selected", async ({
		page,
	}) => {
		// TDD Green phase verification
		await page.goto("/dashboard/1/leads");

		const checkboxes = page.locator("input[type='checkbox'][data-lead-checkbox]");
		await checkboxes.nth(0).check();
		await expect(page.locator("[data-testid='floating-bulk-action-bar']")).toBeHidden();

		await checkboxes.nth(1).check();
		await expect(page.locator("[data-testid='floating-bulk-action-bar']")).toBeVisible();
		await expect(
			page.locator("[data-testid='floating-bulk-action-bar']")
		).toContainText("Đã chọn 2 leads");
	});

	test("should open flyout detail drawer on row click", async ({ page }) => {
		// TDD Green phase verification
		await page.goto("/dashboard/1/leads");

		await page.click("[data-testid='lead-row-lead-1']");
		await expect(page.locator("[data-testid='lead-detail-flyout-drawer']")).toBeVisible();
		await expect(
			page.locator("[data-testid='lead-detail-flyout-drawer']")
		).toContainText("Nguyễn Văn Hùng");
	});
});
