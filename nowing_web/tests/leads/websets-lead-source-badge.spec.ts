import { expect, test } from "../fixtures";

test.describe("Story 41.2: Websets Lead Source Badge & Matrix Filter E2E", () => {
	test.beforeEach(async ({ page }) => {
		// Mock leads endpoint with distinct source types: websets, batdongsan, facebook
		await page.route("**/workspaces/*/leads*", async (route) => {
			await route.fulfill({
				status: 200,
				contentType: "application/json",
				body: JSON.stringify({
					items: [
						{
							id: "11111111-1111-4111-8111-111111111111",
							workspace_id: 1,
							company_name: "Công ty Cổ phần Mytour Việt Nam",
							title: "Khách sạn & Dịch vụ Du lịch trực tuyến",
							source: "websets",
							phone: "0901234567",
							fit_score: 95,
							location: "Quận 1, TP.HCM",
							price: "Liên hệ",
							created_at: new Date().toISOString(),
							extra_metadata: {
								websets: {
									district: { value: "Quận 1", groundingUrl: "https://mytour.vn" },
									verified: { value: "true" },
								},
							},
						},
						{
							id: "22222222-2222-4222-8222-222222222222",
							workspace_id: 1,
							company_name: "Bất Động Sản Hưng Thịnh",
							title: "Căn hộ cao cấp Moonlight Park View",
							source: "batdongsan",
							phone: "0987654321",
							fit_score: 82,
							location: "Bình Tân, TP.HCM",
							price: "3.2 Tỷ",
							created_at: new Date().toISOString(),
						},
						{
							id: "33333333-3333-4333-8333-333333333333",
							workspace_id: 1,
							company_name: "F&B Group Facebook Page",
							title: "Nhượng quyền thương hiệu trà sữa",
							source: "facebook",
							phone: "0912345678",
							fit_score: 78,
							location: "Hà Nội",
							price: "500 Triệu",
							created_at: new Date().toISOString(),
						},
					],
					total: 3,
					limit: 20,
					offset: 0,
				}),
			});
		});
	});

	async function openDock(page: import("@playwright/test").Page) {
		const pill = page.getByRole("button", { name: /open canvas|mở canvas/i });
		const visible = await pill
			.waitFor({ state: "visible", timeout: 5000 })
			.then(() => true)
			.catch(() => false);
		if (visible) await pill.click();
	}

	test("should filter matrix rows when selecting ChainLens Websets source filter", async ({
		page,
		workspace,
	}) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
		await openDock(page);

		const matrix = page.locator("[data-testid='nowing-lead-matrix']");
		await expect(matrix).toBeVisible({ timeout: 15000 });

		// Verify initial state shows all 3 mocked leads
		await expect(page.locator("[data-testid^='lead-row-']")).toHaveCount(3);

		// Open source filter dropdown and select ChainLens Websets
		const filterDropdownTrigger = page
			.getByRole("button", { name: /tất cả nguồn|all sources/i })
			.first();
		await expect(filterDropdownTrigger).toBeVisible();
		await filterDropdownTrigger.click();

		const websetsOption = page.getByRole("button", { name: /ChainLens Websets/i });
		await expect(websetsOption).toBeVisible();
		await websetsOption.click();

		// Verify only Websets lead is visible
		await expect(page.locator("[data-testid^='lead-row-']")).toHaveCount(1);
		await expect(matrix).toContainText("Công ty Cổ phần Mytour Việt Nam");
		await expect(matrix).not.toContainText("Bất Động Sản Hưng Thịnh");
		await expect(matrix).not.toContainText("F&B Group Facebook Page");
	});

	test("should render unified LeadSourceBadge with emerald style for websets in detail drawer", async ({
		page,
		workspace,
	}) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
		await openDock(page);

		// Click on websets lead row to open flyout drawer
		const websetRow = page.locator("[data-testid^='lead-row-']").first();
		await expect(websetRow).toBeVisible();
		await websetRow.click();

		const drawer = page.locator("[data-testid='lead-detail-flyout-drawer']");
		await expect(drawer).toBeVisible({ timeout: 10000 });
		await expect(drawer).toContainText("Công ty Cổ phần Mytour Việt Nam");

		// Locate the LeadSourceBadge in the drawer
		const sourceBadge = drawer.locator("[data-testid='lead-source-badge']");
		await expect(sourceBadge).toBeVisible();
		await expect(sourceBadge).toHaveAttribute("data-source-key", "websets");
		await expect(sourceBadge).toContainText("Websets");

		// Verify emerald color theme classes
		await expect(sourceBadge).toHaveClass(/bg-emerald-50|text-emerald-700/);

		// Verify unmapped enrichments section is rendered
		await expect(drawer.locator("[data-testid='websets-enrichments-section']")).toBeVisible();
		await expect(drawer).toContainText("Quận 1");
	});

	test("should render correct badge style for other sources (batdongsan) and update dynamically", async ({
		page,
		workspace,
	}) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
		await openDock(page);

		// Click on second row (batdongsan lead)
		const bdsRow = page.locator("[data-testid^='lead-row-']").nth(1);
		await expect(bdsRow).toBeVisible();
		await bdsRow.click();

		const drawer = page.locator("[data-testid='lead-detail-flyout-drawer']");
		await expect(drawer).toBeVisible();
		await expect(drawer).toContainText("Bất Động Sản Hưng Thịnh");

		const sourceBadge = drawer.locator("[data-testid='lead-source-badge']");
		await expect(sourceBadge).toBeVisible();
		await expect(sourceBadge).toHaveAttribute("data-source-key", "batdongsan");
		await expect(sourceBadge).toContainText("Batdongsan");
		await expect(sourceBadge).toHaveClass(/bg-rose-50|text-rose-700/);
	});

	test("should close flyout drawer cleanly when close button is clicked", async ({
		page,
		workspace,
	}) => {
		await page.goto(`/dashboard/${workspace.id}/new-chat?mode=leads`);
		await openDock(page);

		// Open drawer
		await page.locator("[data-testid^='lead-row-']").first().click();
		const drawer = page.locator("[data-testid='lead-detail-flyout-drawer']");
		await expect(drawer).toBeVisible();

		// Click close button inside drawer header
		const closeButton = drawer.locator("button:has(svg.lucide-x)").first();
		await expect(closeButton).toBeVisible();
		await closeButton.click();

		// Verify drawer unmounts / is hidden
		await expect(drawer).toBeHidden();
	});
});
